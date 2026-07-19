"""vLLM inference engine adapter."""

import gc
from typing import Any, Dict, Generator, Optional

from runtime.core.errors import EngineUnavailableError, GPUOutOfMemoryError
from runtime.engine.base import BaseInferenceEngine


class VllmInferenceEngine(BaseInferenceEngine):
    """Adapter for the high-performance vLLM engine."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.engine = None

    def _verify_dependencies(self) -> None:
        """Verifies vLLM and torch installations."""
        try:
            import torch
            import vllm
        except ImportError as e:
            raise EngineUnavailableError(
                "vllm",
                details=f"Missing libraries: {e}",
            )

    def load_model(self, model_path: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        self._verify_dependencies()
        from vllm import EngineArgs, LLMEngine

        params = parameters or {}
        gpu_util = params.get("gpu_memory_utilization", 0.90)
        max_model_len = params.get("context_limit", 4096)
        quantization = params.get("quantization")

        # Disable quantization if "none"
        if quantization == "none":
            quantization = None

        try:
            engine_args = EngineArgs(
                model=model_path,
                gpu_memory_utilization=gpu_util,
                max_model_len=max_model_len,
                quantization=quantization,
                trust_remote_code=True,
            )
            # Create the offline LLM Engine
            self.engine = LLMEngine.from_engine_args(engine_args)
            self.current_model_id = model_path
            self.is_loaded = True
        except ValueError as e:
            if "out of memory" in str(e).lower() or "oom" in str(e).lower():
                raise GPUOutOfMemoryError(log_info={"error": str(e)})
            raise e
        except Exception as e:
            raise EngineUnavailableError("vllm", details=str(e))

    def unload_model(self) -> None:
        if self.engine:
            # vLLM occupies GPU VRAM persistently. We delete the engine instance and run GC.
            self.engine = None
        self.current_model_id = None
        self.is_loaded = False

        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def generate_stream(
        self,
        prompt: str,
        generation_params: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        if not self.is_loaded or self.engine is None:
            raise RuntimeError("Model is not loaded.")

        from vllm import SamplingParams

        g_params = generation_params or {}
        sampling_params = SamplingParams(
            temperature=g_params.get("temperature", 0.7),
            top_p=g_params.get("top_p", 0.9),
            max_tokens=g_params.get("max_new_tokens", 512),
        )

        request_id = str(hash(prompt) + hash(time_now := str(gc.time)))
        self.engine.add_request(request_id, prompt, sampling_params)

        last_output_text = ""
        while self.engine.has_unfinished_requests():
            request_outputs = self.engine.step()
            for request_output in request_outputs:
                if request_output.request_id == request_id:
                    # Retrieve the incremental difference (newly generated tokens)
                    full_text = request_output.outputs[0].text
                    new_token = full_text[len(last_output_text) :]
                    last_output_text = full_text
                    if new_token:
                        yield new_token

    def get_status(self) -> Dict[str, Any]:
        return {
            "engine": "vllm",
            "model": self.current_model_id,
            "is_ready": self.is_loaded,
        }

    def is_compatible(self, model_path: str) -> bool:
        # vLLM is generally compatible with PyTorch/safetensors directories
        from pathlib import Path

        path = Path(model_path)
        if path.is_dir():
            return (path / "config.json").exists()
        return True
