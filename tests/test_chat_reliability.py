"""Comprehensive tests for APEX Chat Reliability, Streaming, Stopping Criteria, and Memory."""

import json
import pytest
from fastapi.testclient import TestClient

from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState
from runtime.api.authentication import AuthManager
from runtime.api.queue import RequestQueue
from runtime.api.server import create_app
from runtime.engine.transformers_adapter import TransformersInferenceEngine


class ControlledMockEngine:
    """Mock engine that simulates token generation with configurable stopping behavior."""
    def __init__(self, token_sequence=None):
        self.is_loaded = True
        self.active_model_id = "Qwen/Qwen2.5-0.5B-Instruct"
        self.token_sequence = token_sequence or ["Hello", " ", "world", "!"]
        self.last_prompt = None

    def generate_stream(self, prompt, gen_params=None):
        self.last_prompt = prompt
        for token in self.token_sequence:
            yield token


class MockModelManagerWithEngine:
    def __init__(self, engine=None):
        self.active_engine = engine or ControlledMockEngine()
        self.active_model_id = "Qwen/Qwen2.5-0.5B-Instruct"

    def list_cached_models(self):
        return []


def test_chat_completions_multi_turn_memory(tmp_path):
    """Verify that conversation history is preserved across turns when conversation_id is provided."""
    config = APIConfig(api_enabled=True, enable_auth=False)
    state = RuntimeState(model_loaded="Qwen/Qwen2.5-0.5B-Instruct")
    engine = ControlledMockEngine(["Alice"])
    model_mgr = MockModelManagerWithEngine(engine)
    auth_mgr = AuthManager(config, state)
    queue = RequestQueue(config, state)
    app = create_app(config, state, auth_mgr, queue, model_mgr)
    client = TestClient(app)

    conv_id = "test-session-multi-turn-123"

    # Turn 1: Introduce name
    resp1 = client.post(
        "/v1/chat/completions",
        json={
            "model": "Qwen/Qwen2.5-0.5B-Instruct",
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "My name is Alice."}],
        },
    )
    assert resp1.status_code == 200
    assert resp1.json()["choices"][0]["message"]["content"] == "Alice"

    # Turn 2: Query previous turn using same conversation_id
    resp2 = client.post(
        "/v1/chat/completions",
        json={
            "model": "Qwen/Qwen2.5-0.5B-Instruct",
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "What is my name?"}],
        },
    )
    assert resp2.status_code == 200

    # Verify that turn 2 prompt received by engine includes turn 1 user & assistant turns
    prompt_received = engine.last_prompt
    assert isinstance(prompt_received, list)
    user_turns = [m.get("content", "") for m in prompt_received if m.get("role") == "user"]
    assert "My name is Alice." in user_turns
    assert "What is my name?" in user_turns


def test_chat_completions_streaming_sse_format():
    """Verify that SSE stream delivers valid OpenAI-compatible chunks and ends with [DONE]."""
    config = APIConfig(api_enabled=True, enable_auth=False)
    state = RuntimeState(model_loaded="Qwen/Qwen2.5-0.5B-Instruct")
    engine = ControlledMockEngine(["Hello", " world", "!"])
    model_mgr = MockModelManagerWithEngine(engine)
    auth_mgr = AuthManager(config, state)
    queue = RequestQueue(config, state)
    app = create_app(config, state, auth_mgr, queue, model_mgr)
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "Qwen/Qwen2.5-0.5B-Instruct",
            "stream": True,
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    lines = [line.strip() for line in response.text.split("\n") if line.strip()]
    data_lines = [l for l in lines if l.startswith("data: ")]

    assert len(data_lines) >= 2
    # Verify last data line is [DONE]
    assert data_lines[-1] == "data: [DONE]"

    # Verify JSON structure of first chunk
    first_chunk = json.loads(data_lines[0].replace("data: ", ""))
    assert "choices" in first_chunk
    assert "delta" in first_chunk["choices"][0]


def test_health_endpoint_accurately_reflects_model_status():
    """Verify /health reports model loaded vs loading vs unloaded."""
    config = APIConfig(api_enabled=True, enable_auth=False)
    state = RuntimeState()
    model_mgr = MockModelManagerWithEngine()
    auth_mgr = AuthManager(config, state)
    queue = RequestQueue(config, state)

    # 1. Model unloaded
    model_mgr.active_engine.is_loaded = False
    app = create_app(config, state, auth_mgr, queue, model_mgr)
    client = TestClient(app)

    r1 = client.get("/health")
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["is_model_ready"] is False
    assert data1["model"] in ("unloaded", "loading", "offline")

    # 2. Model loaded
    model_mgr.active_engine.is_loaded = True
    state.model_loaded = "Qwen/Qwen2.5-0.5B-Instruct"
    r2 = client.get("/health")
    data2 = r2.json()
    assert data2["is_model_ready"] is True
    assert data2["model"] == "loaded"


def test_chat_completion_error_when_model_unloaded():
    """Verify 503 is returned if chat is requested while model is not loaded."""
    config = APIConfig(api_enabled=True, enable_auth=False)
    state = RuntimeState()
    model_mgr = MockModelManagerWithEngine()
    model_mgr.active_engine.is_loaded = False
    auth_mgr = AuthManager(config, state)
    queue = RequestQueue(config, state)
    app = create_app(config, state, auth_mgr, queue, model_mgr)
    client = TestClient(app)

    resp = client.post(
        "/v1/chat/completions",
        json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 503


def test_web_interface_endpoint_renders():
    """Verify /chat renders HTML interface with APEX branding and model status."""
    config = APIConfig(api_enabled=True, enable_auth=False)
    state = RuntimeState(model_loaded="Qwen/Qwen2.5-0.5B-Instruct")
    model_mgr = MockModelManagerWithEngine()
    auth_mgr = AuthManager(config, state)
    queue = RequestQueue(config, state)
    app = create_app(config, state, auth_mgr, queue, model_mgr)
    client = TestClient(app)

    resp = client.get("/chat")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "APEX" in resp.text
    assert "status-pill" in resp.text
    assert "apiStatusPill" in resp.text
    assert "modelStatusPill" in resp.text
    assert "conversation" in resp.text.lower()
