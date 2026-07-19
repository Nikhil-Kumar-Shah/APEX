"""Unit tests for inference engines and adapters."""

import pytest
from runtime.engine import get_engine
from runtime.engine.mock_adapter import MockInferenceEngine


def test_get_engine():
    """Checks that the engine factory instantiates correct adapters."""
    config = {"model_id": "test"}

    # Request mock engine
    mock_eng = get_engine("mock", config)
    assert isinstance(mock_eng, MockInferenceEngine)

    # Unknown engine falls back to MockInferenceEngine
    fallback_eng = get_engine("non-existent-engine", config)
    assert isinstance(fallback_eng, MockInferenceEngine)


def test_mock_engine_streaming():
    """Tests the stream generation loop on the MockInferenceEngine."""
    config = {"model_id": "test"}
    engine = get_engine("mock", config)

    # Try generating without loading should fail
    with pytest.raises(RuntimeError):
        list(engine.generate_stream("hello"))

    # Load and generate
    engine.load_model("test-model")
    assert engine.is_loaded

    tokens = list(engine.generate_stream("What is 2+2?"))
    assert len(tokens) > 0
    full_text = "".join(tokens)
    assert "What is 2+2?" in full_text

    # Unload
    engine.unload_model()
    assert not engine.is_loaded
