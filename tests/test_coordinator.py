"""Unit and integration tests for the APEX Decoupled Runtime Coordinator.

Tests the 3-plane decoupled architecture:
1. Control Plane (fast init < 1.5s, hardware detection, local storage default)
2. Model Execution Plane (cache lookup, download, load, warm-up, authoritative states)
3. Connectivity Plane (API, tunnel, health checks, 503 while model loading)
4. Parallel execution and failure isolation
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from runtime.api.chat import router as chat_router
from runtime.config.profile import detect_environment_hardware
from runtime.orchestrator.coordinator import (
    APIStatus,
    ControlPlaneStatus,
    ModelExecutionStatus,
    RuntimeCoordinator,
    SystemStatus,
    TunnelStatus,
)


# ── 1. Status Model & Readiness Properties Tests ─────────────────────────────

def test_coordinator_initial_states():
    """Verify initial statuses of all 3 planes upon coordinator creation."""
    coordinator = RuntimeCoordinator()
    assert coordinator.control_status == ControlPlaneStatus.NOT_INITIALIZED
    assert coordinator.model_status == ModelExecutionStatus.MODEL_NOT_CONFIGURED
    assert coordinator.api_status == APIStatus.API_NOT_STARTED
    assert coordinator.tunnel_status == TunnelStatus.TUNNEL_NOT_STARTED
    assert coordinator.is_control_plane_ready is False
    assert coordinator.is_model_ready is False
    assert coordinator.is_api_ready is False
    assert coordinator.is_tunnel_ready is False
    assert coordinator.is_fully_operational is False
    assert coordinator.system_status == SystemStatus.STOPPED


def test_coordinator_system_status_transitions():
    """Test overall system status evaluation across different plane states."""
    coordinator = RuntimeCoordinator()
    coordinator.control_status = ControlPlaneStatus.READY
    coordinator.api_status = APIStatus.READY
    coordinator.tunnel_status = TunnelStatus.READY

    # While model is loading, system status is DEGRADED (connectable, but inference pending)
    coordinator.model_status = ModelExecutionStatus.LOADING
    assert coordinator.system_status == SystemStatus.DEGRADED
    assert coordinator.is_fully_operational is False

    # When model is ready, system status is READY (or OPERATIONAL)
    coordinator.model_status = ModelExecutionStatus.READY
    assert coordinator.system_status == SystemStatus.READY
    assert coordinator.is_fully_operational is True

    # When model fails, system status is DEGRADED (API still up)
    coordinator.model_status = ModelExecutionStatus.FAILED
    assert coordinator.system_status == SystemStatus.DEGRADED

    # When API fails, system status is FAILED
    coordinator.api_status = APIStatus.FAILED
    assert coordinator.system_status == SystemStatus.FAILED


# ── 2. Control Plane Initialization Tests ────────────────────────────────────

def test_control_plane_fast_initialization(tmp_path):
    """Test that Control Plane initialization completes quickly without blocking."""
    coordinator = RuntimeCoordinator(project_root=tmp_path)

    start_t = time.perf_counter()
    status = coordinator.init_control_plane()
    elapsed = time.perf_counter() - start_t

    # Must complete in well under 1.5 seconds (target < 1.0s)
    assert elapsed < 1.5
    assert status == ControlPlaneStatus.READY
    assert coordinator.is_control_plane_ready is True
    assert coordinator.hardware_info is not None
    assert coordinator.storage_info is not None

    # Verify storage defaults to local cache under project root, NOT Google Drive
    cache_path = coordinator.storage_info["cache_path"]
    assert str(tmp_path / "cache") in str(cache_path)
    assert coordinator.storage_info["google_drive_mounted"] is False


def test_control_plane_hardware_detection():
    """Verify hardware detection executes cleanly and populates system metrics."""
    hw = detect_environment_hardware()
    assert "device" in hw
    assert "gpu_name" in hw
    assert "cuda_available" in hw
    assert "ram_total_gb" in hw
    assert "ram_available_gb" in hw
    assert "is_colab" in hw
    assert isinstance(hw["cuda_available"], bool)


# ── 3. Model Execution Plane Tests ───────────────────────────────────────────

def test_model_plane_execution_mocked(tmp_path):
    """Test model plane states transition cleanly through download, load, and ready."""
    coordinator = RuntimeCoordinator(project_root=tmp_path)
    coordinator.init_control_plane()

    # Mock model manager
    mock_model_mgr = MagicMock()
    mock_model_mgr.is_cached.return_value = False
    mock_model_mgr.download_model.return_value = tmp_path / "models" / "mock"
    mock_model_mgr.load_model.return_value = True

    coordinator.model_manager = mock_model_mgr

    status = coordinator.start_model_plane("Qwen/Qwen2.5-0.5B", precision="float16")

    assert status == ModelExecutionStatus.READY
    assert coordinator.is_model_ready is True
    assert coordinator.model_repo_id == "Qwen/Qwen2.5-0.5B"
    mock_model_mgr.download_model.assert_called_once()
    mock_model_mgr.load_model.assert_called_once()


def test_model_plane_cache_hit_skips_download(tmp_path):
    """Test that when model is already cached, download step is skipped."""
    coordinator = RuntimeCoordinator(project_root=tmp_path)
    coordinator.init_control_plane()

    mock_model_mgr = MagicMock()
    mock_model_mgr.is_cached.return_value = True
    mock_model_mgr.load_model.return_value = True

    coordinator.model_manager = mock_model_mgr

    status = coordinator.start_model_plane("Qwen/Qwen2.5-0.5B")

    assert status == ModelExecutionStatus.READY
    mock_model_mgr.download_model.assert_not_called()
    mock_model_mgr.load_model.assert_called_once()


def test_model_plane_failure_isolation(tmp_path):
    """Test that model load failure marks model as FAILED without raising uncaught exception."""
    coordinator = RuntimeCoordinator(project_root=tmp_path)
    coordinator.init_control_plane()

    mock_model_mgr = MagicMock()
    mock_model_mgr.is_cached.return_value = False
    mock_model_mgr.download_model.side_effect = RuntimeError("Disk full during model download")

    coordinator.model_manager = mock_model_mgr

    status = coordinator.start_model_plane("Qwen/Qwen2.5-0.5B")

    assert status == ModelExecutionStatus.FAILED
    assert coordinator.is_model_ready is False
    assert "Disk full" in coordinator.model_error


# ── 4. Connectivity Plane Tests ──────────────────────────────────────────────

def test_connectivity_plane_start_mocked(tmp_path):
    """Test connectivity plane initialization with mock API and Tunnel managers."""
    coordinator = RuntimeCoordinator(project_root=tmp_path)
    coordinator.init_control_plane()

    mock_api_mgr = MagicMock()
    mock_api_mgr.is_running = True
    mock_api_mgr.port = 8000
    mock_api_mgr.health_status = {"status": "ok"}

    coordinator.api_manager = mock_api_mgr

    # Mock cloudflare tunnel manager inside start_connectivity_plane
    with patch("runtime.api.tunnel.TunnelManager") as MockTunnelClass:
        mock_tunnel = MagicMock()
        mock_tunnel.start.return_value = "https://mock-apex-test.trycloudflare.com"
        mock_tunnel.tunnel_url = "https://mock-apex-test.trycloudflare.com"
        MockTunnelClass.return_value = mock_tunnel

        api_stat, tun_stat = coordinator.start_connectivity_plane(
            enable_tunnel=True,
            tunnel_provider="cloudflare",
            api_port=8000,
        )

        assert api_stat == APIStatus.READY
        assert tun_stat == TunnelStatus.READY
        assert coordinator.is_api_ready is True
        assert coordinator.is_tunnel_ready is True
        assert coordinator.tunnel_url == "https://mock-apex-test.trycloudflare.com"


# ── 5. HTTP 503 When Model Is Not Ready ──────────────────────────────────────

def test_chat_endpoint_returns_503_when_model_loading():
    """Verify that /v1/chat/completions returns HTTP 503 with Retry-After when model not ready."""
    app = FastAPI()
    app.include_router(chat_router)

    # Mock model manager where model is NOT ready
    mock_model_mgr = MagicMock()
    mock_model_mgr.active_engine = None  # No loaded engine!
    app.state.model_manager = mock_model_mgr

    client = TestClient(app)

    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Hello APEX"}],
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 503
    assert response.headers.get("Retry-After") == "5"
    data = response.json()
    assert "detail" in data
    assert "loading" in data["detail"].lower() or "not ready" in data["detail"].lower()


# ── 6. Parallel Execution Tests ──────────────────────────────────────────────

def test_launch_parallel_coordination(tmp_path):
    """Test parallel launch orchestrating Control, Model, and Connectivity planes concurrently."""
    coordinator = RuntimeCoordinator(project_root=tmp_path)

    mock_model_mgr = MagicMock()
    mock_model_mgr.is_cached.return_value = True
    mock_model_mgr.load_model.return_value = True
    coordinator.model_manager = mock_model_mgr

    mock_api_mgr = MagicMock()
    mock_api_mgr.is_running = True
    mock_api_mgr.port = 8000
    mock_api_mgr.health_status = {"status": "ok"}
    coordinator.api_manager = mock_api_mgr

    with patch("runtime.api.tunnel.TunnelManager") as MockTunnelClass:
        mock_tunnel = MagicMock()
        mock_tunnel.start.return_value = "https://mock-apex-test.trycloudflare.com"
        mock_tunnel.tunnel_url = "https://mock-apex-test.trycloudflare.com"
        MockTunnelClass.return_value = mock_tunnel

        results = coordinator.launch_parallel(
            model_id="Qwen/Qwen2.5-0.5B",
            enable_tunnel=True,
            tunnel_provider="cloudflare",
            api_port=8000,
            sync=True,
        )

        assert results["control_plane"] == ControlPlaneStatus.READY
        assert results["model_plane"] == ModelExecutionStatus.READY
        assert results["api_status"] == APIStatus.READY
        assert results["tunnel_status"] == TunnelStatus.READY
        assert coordinator.is_fully_operational is True


def test_coordinator_shutdown(tmp_path):
    """Test clean shutdown of all planes."""
    coordinator = RuntimeCoordinator(project_root=tmp_path)
    coordinator.init_control_plane()

    mock_model_mgr = MagicMock()
    coordinator.model_manager = mock_model_mgr

    mock_api_mgr = MagicMock()
    mock_api_mgr.is_running = True
    coordinator.api_manager = mock_api_mgr

    mock_tunnel = MagicMock()
    coordinator.tunnel_manager = mock_tunnel

    coordinator.shutdown(sync=True)

    mock_model_mgr.unload_model.assert_called_once()
    mock_api_mgr.stop.assert_called_once()
    mock_tunnel.stop.assert_called_once()
    assert coordinator.control_status == ControlPlaneStatus.NOT_INITIALIZED
    assert coordinator.model_status == ModelExecutionStatus.MODEL_NOT_CONFIGURED
    assert coordinator.api_status == APIStatus.API_NOT_STARTED
    assert coordinator.tunnel_status == TunnelStatus.TUNNEL_NOT_STARTED
