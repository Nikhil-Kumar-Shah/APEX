"""Tests for APEX API Subsystem."""

import pytest
from fastapi.testclient import TestClient

from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState
from runtime.api.manager import APIManager
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
    
    # Missing Auth
    response = client.get("/v1/models")
    assert response.status_code == 401
    
    # Invalid Auth
    response = client.get("/v1/models", headers={"Authorization": "Bearer bad_secret"})
    assert response.status_code == 403
    
    # Valid Auth
    response = client.get("/v1/models", headers={"Authorization": "Bearer secret"})
    assert response.status_code == 200

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
    data = response.json()
    assert data["choices"][0]["message"]["content"] == "Hello World! I am APEX."
