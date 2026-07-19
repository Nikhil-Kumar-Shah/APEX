"""llama.cpp (GGUF) inference engine adapter."""

import gc
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from runtime.core.errors import EngineUnavailableError, GPUOutOfMemoryError
from runtime.engine.base import BaseInferenceEngine


class LlamaCppInferenceEngine(BaseInferenceEngine):
    """Adapter for the llama-cpp-python GGUF runner."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model = None

    def _verify_dependencies(self) -> None:
        """Verifies llama-cpp-python installation."""
        try:
            import llama_cpp
        except ImportError as e:
            raise EngineUnavailableError(
                "llama-cpp-python",
                details=f"Missing libraries: {e}",
            )

    def load_model(self, model_path: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        self._verify_dependencies()
        import llama_cpp

        params = parameters or {}
        n_ctx = params.get("context_limit", 2048)

        # In Colab, we default to full GPU offload if CUDA is active
        n_gpu_layers = params.get("n_gpu_layers", -1)

        try:
            # Load the GGUF model binary
            self.model = llama_cpp.Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                verbose=False,
            )
            self.current_model_id = model_path
            self.is_loaded = True
        except ValueError as e:
            if "out of memory" in str(e).lower() or "oom" in str(e).lower():
                raise GPUOutOfMemoryError(log_info={"error": str(e)})
            raise e
        except Exception as e:
            raise EngineUnavailableError("llama-cpp-python", details=str(e))

    def unload_model(self) -> None:
        self.model = None
        self.current_model_id = None
        self.is_loaded = False
        gc.collect()

    def generate_stream(
        self,
        prompt: str,
        generation_params: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        if not self.is_loaded or self.model is None:
            raise RuntimeError("Model is not loaded.")

        g_params = generation_params or {}
        temperature = g_params.get("temperature", 0.7)
        top_p = g_params.get("top_p", 0.9)
        max_tokens = g_params.get("max_new_tokens", 512)

        # Call the completion API streamingly
        stream = self.model.create_completion(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=True,
        )

        for chunk in stream:
            text = chunk["choices"][0]["text"]
            if text:
                yield text

    def get_status(self) -> Dict[str, Any]:
        return {
            "engine": "llama.cpp",
            "model": self.current_model_id,
            "is_ready": self.is_loaded,
        }

    def is_compatible(self, model_path: str) -> bool:
        # llama.cpp is only compatible with GGUF files
        return Path(model_path).suffix.lower() == ".gguf"
