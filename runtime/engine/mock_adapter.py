"""Mock inference engine for tests and local emulation."""

import time
from typing import Any, Dict, Generator, Optional

from runtime.engine.base import BaseInferenceEngine


class MockInferenceEngine(BaseInferenceEngine):
    """Simulates a model inference engine for testing without external GPU/ML dependencies."""

    def load_model(self, model_path: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        self.current_model_id = model_path
        self.is_loaded = True

    def unload_model(self) -> None:
        self.current_model_id = None
        self.is_loaded = False

    def generate_stream(
        self,
        prompt: str,
        generation_params: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        if not self.is_loaded:
            raise RuntimeError("Model is not loaded.")

        # Simulate stream of token responses
        response_text = f"Mock response to your prompt: '{prompt}'. Generating token stream..."
        words = response_text.split(" ")

        for i, word in enumerate(words):
            # Simulate a small delay for token generation
            time.sleep(0.02)
            yield word + (" " if i < len(words) - 1 else "")

    def get_status(self) -> Dict[str, Any]:
        return {
            "engine": "mock",
            "model": self.current_model_id,
            "vram_used_mb": 512 if self.is_loaded else 0,
            "ram_used_mb": 256,
            "is_ready": self.is_loaded,
        }

    def is_compatible(self, model_path: str) -> bool:
        return True
