"""Tests for APEX API Subsystem — including startup lifecycle verification."""

import time
import socket
import threading
import pytest
from fastapi.testclient import TestClient

from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState, APIStatus
from runtime.api.manager import APIManager, _is_port_occupied, _find_free_port
from runtime.api.authentication import AuthManager
from runtime.api.queue import RequestQueue


class MockModelManager:
    def list_cached_models(self):
        return []


@pytest.fixture
def mock_managers():
    config = APIConfig(api_enabled=True, enable_auth=False)
    state = RuntimeState(model_loaded="Qwen/Qwen2.5-0.5B")
    model_manager = MockModelManager()
    auth_manager = AuthManager(config, state)
    queue = RequestQueue(config, state)
    return config, state, auth_manager, queue, model_manager


# ── Endpoint Tests ────────────────────────────────────────────────────────

def test_api_health_endpoint(mock_managers):
    config, state, auth_manager, queue, model_manager = mock_managers
    from runtime.api.server import create_app
    app = create_app(config, state, auth_manager, queue, model_manager)
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model_loaded"] == "Qwen/Qwen2.5-0.5B"


def test_api_auth_rejection():
    config = APIConfig(enable_auth=True, api_key="secret")
    state = RuntimeState()
    auth_manager = AuthManager(config, state)
    queue = RequestQueue(config, state)
    model_manager = MockModelManager()
    from runtime.api.server import create_app
    app = create_app(config, state, auth_manager, queue, model_manager)
    client = TestClient(app)

    # Missing Auth header
    resp = client.get("/v1/models")
    assert resp.status_code == 401

    # Invalid token
    resp = client.get("/v1/models", headers={"Authorization": "Bearer bad_secret"})
    assert resp.status_code == 403

    # Valid token
    resp = client.get("/v1/models", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 200


def test_api_chat_completions(mock_managers):
    config, state, auth_manager, queue, model_manager = mock_managers
    from runtime.api.server import create_app
    app = create_app(config, state, auth_manager, queue, model_manager)
    client = TestClient(app)
    response = client.post("/v1/chat/completions", json={
        "model": "Qwen/Qwen2.5-0.5B",
        "messages": [{"role": "user", "content": "Hello"}]
    })
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Hello World! I am APEX."


# ── Port Utility Tests ────────────────────────────────────────────────────

def test_is_port_occupied_free():
    """A port with nothing on it should not report as occupied."""
    free_port = _find_free_port(19800)
    assert free_port is not None
    assert not _is_port_occupied("127.0.0.1", free_port)


def test_is_port_occupied_bound():
    """A port with a listener should report as occupied."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.listen(1)
    try:
        assert _is_port_occupied("127.0.0.1", port)
    finally:
        srv.close()


def test_find_free_port():
    """find_free_port should return a port that is not occupied."""
    port = _find_free_port(19900)
    assert port is not None
    assert not _is_port_occupied("127.0.0.1", port)


# ── APIStatus State Tests ─────────────────────────────────────────────────

def test_api_status_enum_values():
    """Verify all expected status values exist."""
    assert APIStatus.STOPPED.value == "STOPPED"
    assert APIStatus.STARTING.value == "STARTING"
    assert APIStatus.VERIFYING.value == "VERIFYING"
    assert APIStatus.RUNNING.value == "RUNNING"
    assert APIStatus.FAILED.value == "FAILED"


def test_runtime_state_api_running_property():
    """api_running property is only True when status is RUNNING."""
    state = RuntimeState()
    assert state.api_running is False

    state.api_status = APIStatus.RUNNING
    assert state.api_running is True

    state.api_status = APIStatus.FAILED
    assert state.api_running is False


# ── Manager Lifecycle Tests ───────────────────────────────────────────────

def test_api_manager_fails_on_occupied_unhealthy_port():
    """
    When a port is occupied by something unhealthy (e.g. a raw TCP listener
    that doesn't speak HTTP) AND no alternative port is free in the search
    range, start() should return False and api_status should be FAILED.
    """
    # Occupy 10 consecutive ports with raw TCP servers so auto-selection fails
    servers = []
    base = 19700
    for p in range(base, base + 11):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", p))
            s.listen(1)
            servers.append(s)
        except OSError:
            pass

    try:
        config = APIConfig(api_enabled=True, internal_port=base)
        state = RuntimeState()
        mgr = APIManager(config, state, MockModelManager())
        result = mgr.start()
        # Should fail: port blocked + no free alternative in range
        assert result is False
        assert state.api_status == APIStatus.FAILED
    finally:
        for s in servers:
            try:
                s.close()
            except Exception:
                pass


def test_api_manager_disabled():
    """When api_enabled=False, start() returns False without changing state."""
    config = APIConfig(api_enabled=False)
    state = RuntimeState()
    mgr = APIManager(config, state, MockModelManager())
    result = mgr.start()
    assert result is False
    assert state.api_status == APIStatus.STOPPED
