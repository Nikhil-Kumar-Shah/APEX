"""Model manager orchestrator — APEX V1 (Hugging Face + Transformers only)."""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.core.errors import (
    ModelNotFoundError,
    UnsupportedArchitectureError,
)
from runtime.engine import BaseInferenceEngine, get_engine
from runtime.model.cache import CacheManager
from runtime.model.downloader import ModelDownloader


logger = logging.getLogger("runtime.model")

# Strict V1 regex: only "org/model-name" style Hugging Face IDs
_HF_MODEL_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+$")

# Patterns explicitly rejected in V1
_REJECTED_PATTERNS = [
    (".gguf", "GGUF format"),
    (".ggml", "GGML format"),
    (".bin", "Raw binary weights"),
    ("hf://", "HF URI scheme"),
    ("hf download", "CLI download command"),
    ("ollama", "Ollama models"),
    ("modelscope", "ModelScope models"),
]


def _validate_model_id(model_id: str) -> None:
    """Validates that the model_id is a clean Hugging Face repo identifier.

    Raises:
        UnsupportedArchitectureError: If the input doesn't match V1 constraints.
    """
    stripped = model_id.strip()

    # Check against explicitly rejected patterns
    for pattern, label in _REJECTED_PATTERNS:
        if pattern in stripped.lower():
            raise UnsupportedArchitectureError(
                model_id=stripped,
                engine_name="transformers",
                arch=label,
                log_info={
                    "input": stripped,
                    "rejected_pattern": pattern,
                    "message": (
                        f"Unsupported model source.\n"
                        f"APEX Version 1 only supports Hugging Face model IDs.\n"
                        f"Example: Qwen/Qwen2.5-1.5B-Instruct"
                    ),
                },
            )

    # Validate format
    if not _HF_MODEL_ID_PATTERN.match(stripped):
        raise UnsupportedArchitectureError(
            model_id=stripped,
            engine_name="transformers",
            arch="unknown",
            log_info={
                "input": stripped,
                "message": (
                    f"Unsupported model source.\n"
                    f"APEX Version 1 only supports Hugging Face model IDs.\n"
                    f"Example: Qwen/Qwen2.5-1.5B-Instruct"
                ),
            },
        )


class ModelManager:
    """Orchestrates model downloads, cache tracking, and engine execution lifecycles.

    APEX V1 Constraints:
        - Only Hugging Face Hub model IDs are accepted.
        - Only the Transformers engine is used for loading.
        - No GGUF, llama.cpp, vLLM, or Ollama support.
    """

    def __init__(self, cache_dir: Path, hf_token: Optional[str] = None):
        """Initializes the ModelManager.

        Args:
            cache_dir: Root cache directory for models.
            hf_token: Optional Hugging Face Token.
        """
        self.cache_manager = CacheManager(cache_dir)
        self.downloader = ModelDownloader(cache_dir, token=hf_token)
        self.active_engine: Optional[BaseInferenceEngine] = None
        self.active_model_id: Optional[str] = None

    def list_cached_models(self) -> List[Dict[str, Any]]:
        """Lists metadata of currently cached models."""
        return self.cache_manager.list_cached_models()

    def download_model(self, model_id: str) -> Path:
        """Downloads a model if not already cached.

        Args:
            model_id: The Hugging Face repo ID (e.g. 'Qwen/Qwen2.5-1.5B-Instruct').

        Returns:
            Path: The local directory containing the model files.
        """
        _validate_model_id(model_id)

        target_path = self.cache_manager.get_model_cache_path(model_id)

        if self.cache_manager.is_cached(model_id):
            logger.info(f"Model '{model_id}' is already cached at: {target_path}", extra={"prefix": "CACHE"})
            return target_path

        logger.info(f"Starting download", extra={"prefix": "MODEL"})
        logger.info(f"Repository: {model_id}", extra={"prefix": "MODEL"})
        self.downloader.download(model_id, target_path)
        logger.info(f"Download complete for '{model_id}'", extra={"prefix": "SUCCESS"})
        return target_path

    def load_model(
        self,
        model_id: str,
        engine_override: Optional[str] = None,
        **kwargs,
    ) -> BaseInferenceEngine:
        """Downloads (if needed) and loads a model into memory using the Transformers engine.

        Args:
            model_id: Hugging Face model repository ID.
            engine_override: Ignored in V1 (always uses 'transformers'). Kept for test compatibility.
            **kwargs: Additional parameters forwarded to the engine.

        Returns:
            BaseInferenceEngine: The active inference engine loaded with the model.
        """
        _validate_model_id(model_id)

        if self.active_model_id == model_id and self.active_engine is not None:
            logger.info(f"Model '{model_id}' is already loaded.", extra={"prefix": "MODEL"})
            return self.active_engine

        # V1: Always use transformers (allow 'mock' override for tests only)
        selected_engine = "transformers"
        if engine_override == "mock":
            selected_engine = "mock"

        logger.info(f"Loading model...", extra={"prefix": "MODEL"})
        logger.info(f"Repository: {model_id}", extra={"prefix": "MODEL"})
        logger.info(f"Engine: {selected_engine}", extra={"prefix": "MODEL"})

        # 1. Download if missing
        local_path = self.download_model(model_id)
        load_path = str(local_path)

        # 2. Check GPU
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                vram_gb = torch.cuda.get_device_properties(0).total_mem / (1024**3)
                logger.info(f"GPU: {gpu_name} ({vram_gb:.1f} GB VRAM)", extra={"prefix": "GPU"})
                logger.info(f"CUDA available", extra={"prefix": "GPU"})
            else:
                logger.warning(f"No GPU detected. Using CPU fallback.", extra={"prefix": "GPU"})
        except ImportError:
            logger.warning("PyTorch not available for GPU detection.", extra={"prefix": "GPU"})

        # 3. Unload any active model first
        self.unload_model()

        # 4. Instantiate and load engine
        engine_config = {
            "model_id": model_id,
            "precision": kwargs.get("precision", "float16"),
        }

        try:
            engine = get_engine(selected_engine, engine_config)

            logger.info(f"Loading tokenizer...", extra={"prefix": "TOKENIZER"})
            logger.info(f"Loading model weights...", extra={"prefix": "MODEL"})

            engine.load_model(load_path, parameters=engine_config)

            self.active_engine = engine
            self.active_model_id = model_id

            logger.info(f"Model ready: {model_id}", extra={"prefix": "SUCCESS"})
            return engine
        except Exception as e:
            logger.error(f"Failed to load model '{model_id}': {e}", exc_info=True, extra={"prefix": "ERROR"})
            self.unload_model()
            raise e

    def unload_model(self) -> None:
        """Safely unloads the active model and releases all engine assets."""
        if self.active_engine:
            logger.info(f"Unloading active model '{self.active_model_id}'...", extra={"prefix": "MODEL"})
            try:
                self.active_engine.unload_model()
            except Exception as e:
                logger.warning(f"Error while unloading engine: {e}", extra={"prefix": "WARNING"})
            self.active_engine = None
        self.active_model_id = None

    def get_status(self) -> Dict[str, Any]:
        """Provides status details of the active model and cache metrics.

        Returns:
            Dict[str, Any]: Status attributes.
        """
        status: Dict[str, Any] = {
            "active_model_id": self.active_model_id,
            "is_loaded": self.active_model_id is not None,
            "cache_size_gb": self.cache_manager.get_cache_size_bytes() / (1024**3),
            "cached_models_count": len(self.list_cached_models()),
        }
        if self.active_engine:
            status["engine_status"] = self.active_engine.get_status()
        return status
