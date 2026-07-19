"""Hugging Face Transformers inference engine adapter."""

import gc
import sys
from typing import Any, Dict, Generator, Optional

from runtime.core.errors import EngineUnavailableError, GPUOutOfMemoryError
from runtime.engine.base import BaseInferenceEngine


class TransformersInferenceEngine(BaseInferenceEngine):
    """Adapter for the Hugging Face Transformers library."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model = None
        self.tokenizer = None
        self.device = "cpu"

    def _verify_dependencies(self) -> None:
        """Verifies that PyTorch and Transformers are installed."""
        try:
            import torch
            import transformers
        except ImportError as e:
            raise EngineUnavailableError(
                "transformers",
                details=f"Missing libraries: {e}",
            )

    def load_model(self, model_path: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        self._verify_dependencies()
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        params = parameters or {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Determine precision and device mappings
        torch_dtype = torch.float16 if self.device == "cuda" else torch.float32
        precision = params.get("precision", "float16")
        if precision == "bfloat16" and torch.cuda.is_bf16_supported():
            torch_dtype = torch.bfloat16

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)

            # Defensive loading against OOM
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch_dtype,
                device_map="auto" if self.device == "cuda" else None,
                low_cpu_mem_usage=True,
            )
            self.current_model_id = model_path
            self.is_loaded = True
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                raise GPUOutOfMemoryError(log_info={"error": str(e)})
            raise e

    def unload_model(self) -> None:
        self.model = None
        self.tokenizer = None
        self.current_model_id = None
        self.is_loaded = False

        # Run garbage collection and empty CUDA cache
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
        if not self.is_loaded or self.model is None or self.tokenizer is None:
            raise RuntimeError("Model is not loaded.")

        import torch
        from transformers import TextIteratorStreamer
        from threading import Thread

        # Prepare parameters
        g_params = generation_params or {}
        max_new_tokens = g_params.get("max_new_tokens", 512)
        temperature = g_params.get("temperature", 0.7)
        top_p = g_params.get("top_p", 0.9)

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)

        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=max_new_tokens,
            do_sample=temperature > 0.0,
            temperature=temperature if temperature > 0.0 else None,
            top_p=top_p if temperature > 0.0 else None,
        )

        # Run model generation in a background thread to allow streamer consumption
        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        try:
            for new_text in streamer:
                yield new_text
        finally:
            thread.join()

    def get_status(self) -> Dict[str, Any]:
        status = {
            "engine": "transformers",
            "model": self.current_model_id,
            "is_ready": self.is_loaded,
            "device": self.device,
        }
        if self.device == "cuda":
            try:
                import torch

                status["vram_allocated_mb"] = torch.cuda.memory_allocated() / (1024 * 1024)
                status["vram_reserved_mb"] = torch.cuda.memory_reserved() / (1024 * 1024)
            except (ImportError, Exception):
                pass
        return status

    def is_compatible(self, model_path: str) -> bool:
        # Check standard config file naming
        from pathlib import Path

        path = Path(model_path)
        if path.is_dir():
            return (path / "config.json").exists()
        return True  # Remote HF repos are assumed compatible until checked
