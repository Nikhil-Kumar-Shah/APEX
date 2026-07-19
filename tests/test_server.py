"""Unit tests for the server, router, and API layer."""

import json
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from unittest.mock import MagicMock, patch

from runtime.core.health import HealthMonitor
from runtime.model.manager import ModelManager
from runtime.server.app import create_app


@pytest.fixture
def mock_managers(tmp_path: Path):
    """Fixture supplying mock ModelManager and HealthMonitor configurations."""
    # Create model manager with mock active model
    model_mgr = ModelManager(tmp_path)
    model_mgr.active_model_id = "qwen/qwen2.5-7b"
    model_mgr.active_engine = MagicMock()
    
    # Configure mock engine generate stream
    def mock_generator(prompt, params):
        yield "Hello"
        yield " world"

    model_mgr.active_engine.generate_stream.side_effect = mock_generator

    health_mon = HealthMonitor(tmp_path, model_mgr)

    return model_mgr, health_mon


@pytest.fixture
def client(mock_managers):
    """Fixture supplying a TestClient instance."""
    model_mgr, health_mon = mock_managers
    app = create_app(
        model_manager=model_mgr,
        health_monitor=health_mon,
        server_port=8000,
        queue_max_size=2,  # small queue for testing backpressure
    )
    # Trigger startup/shutdown lifespan hooks using TestClient context manager
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    """Verifies the health endpoint responds successfully."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_endpoint(client):
    """Verifies that the server diagnostics payload returns expected fields."""
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "uptime_seconds" in data
    assert "disk" in data
    assert "ram" in data
    assert "gpu" in data
    assert "server" in data
    assert "queue" in data


def test_list_models_endpoint(client):
    """Verifies model listing responds with active models."""
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) >= 1
    assert data["data"][0]["id"] == "qwen/qwen2.5-7b"


def test_chat_completions_json(client):
    """Tests non-streaming chat completions response."""
    payload = {
        "model": "qwen/qwen2.5-7b",
        "messages": [{"role": "user", "content": "Hello!"}],
        "stream": False,
        "temperature": 0.7,
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "choices" in data
    assert data["choices"][0]["message"]["content"] == "Hello world"
    assert data["choices"][0]["message"]["role"] == "assistant"


def test_chat_completions_stream(client):
    """Tests streaming SSE completion response chunks."""
    payload = {
        "model": "qwen/qwen2.5-7b",
        "messages": [{"role": "user", "content": "Hello!"}],
        "stream": True,
        "temperature": 0.7,
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    
    # Read streamed text content chunks
    lines = response.text.split("\n\n")
    chunks = [line for line in lines if line.startswith("data: ")]
    
    assert len(chunks) >= 3  # "Hello", " world", and "[DONE]"
    assert chunks[-1] == "data: [DONE]"
    
    # Parse first chunk content
    first_json = json.loads(chunks[0][6:])
    assert first_json["choices"][0]["delta"]["content"] == "Hello"


def test_queue_full_rejection(client, mock_managers):
    """Tests queue capacity backpressure rejection."""
    model_mgr, health_mon = mock_managers
    
    # Configure the mock engine generator to block/delay to simulate slow generation
    import time
    def slow_generator(prompt, params):
        time.sleep(2)
        yield "Delayed"

    model_mgr.active_engine.generate_stream.side_effect = slow_generator

    # Create app with queue limit of 1
    app = create_app(
        model_manager=model_mgr,
        health_monitor=health_mon,
        server_port=8000,
        queue_max_size=1,
    )

    with TestClient(app) as test_client:
        payload = {
            "model": "qwen/qwen2.5-7b",
            "messages": [{"role": "user", "content": "Slow Request"}],
            "stream": False,
        }
        
        # Mock the request_queue size directly to simulate a full queue (limit=1)
        with patch.object(app.state.queue_manager._queue, "qsize", return_value=1):
            response = test_client.post("/v1/chat/completions", json=payload)
            assert response.status_code == 429
            data = response.json()
            assert data["error"]["code"] == "queue_full"

