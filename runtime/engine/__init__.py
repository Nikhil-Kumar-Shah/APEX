"""Engine package and factory module."""

from typing import Any, Dict

from runtime.engine.base import BaseInferenceEngine
from runtime.engine.llama_cpp_adapter import LlamaCppInferenceEngine
from runtime.engine.mock_adapter import MockInferenceEngine
from runtime.engine.transformers_adapter import TransformersInferenceEngine
from runtime.engine.vllm_adapter import VllmInferenceEngine

ENGINE_MAP = {
    "transformers": TransformersInferenceEngine,
    "vllm": VllmInferenceEngine,
    "llama.cpp": LlamaCppInferenceEngine,
    "mock": MockInferenceEngine,
}


def get_engine(engine_name: str, config: Dict[str, Any]) -> BaseInferenceEngine:
    """Factory function to instantiate the correct inference engine.

    Falls back to 'mock' if the engine name is unrecognized.

    Args:
        engine_name: The name of the engine ('transformers', 'vllm', 'llama.cpp', 'mock').
        config: Configuration dictionary.

    Returns:
        BaseInferenceEngine: An instantiated inference engine adapter.
    """
    key = engine_name.lower().strip()
    cls = ENGINE_MAP.get(key, MockInferenceEngine)
    return cls(config)


__all__ = [
    "BaseInferenceEngine",
    "TransformersInferenceEngine",
    "VllmInferenceEngine",
    "LlamaCppInferenceEngine",
    "MockInferenceEngine",
    "get_engine",
]
