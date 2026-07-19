"""Model manager orchestrator."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from runtime.config.profile import get_profile
from runtime.core.errors import (
    EngineUnavailableError,
    ModelNotFoundError,
    UnsupportedArchitectureError,
)
from runtime.engine import BaseInferenceEngine, get_engine
from runtime.model.cache import CacheManager
from runtime.model.downloader import ModelDownloader


class ModelManager:
    """Orchestrates model downloads, cache tracking, and engine execution lifecycles."""

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
        self.logger = logging.getLogger("runtime.model")

    def list_cached_models(self) -> List[Dict[str, Any]]:
        """Lists metadata of currently cached models."""
        return self.cache_manager.list_cached_models()

    def download_model(self, model_id: str, filename_pattern: Optional[str] = None) -> Path:
        """Downloads a model if not already cached.

        Args:
            model_id: The Hugging Face repo ID.
            filename_pattern: Optional filter pattern (e.g. *.gguf).

        Returns:
            Path: The local directory containing the model files.
        """
        target_path = self.cache_manager.get_model_cache_path(model_id)

        if self.cache_manager.is_cached(model_id):
            self.logger.info(f"Model '{model_id}' is already cached at: {target_path}")
            return target_path

        self.logger.info(f"Initiating download of model '{model_id}'...")
        self.downloader.download(model_id, target_path, filename_pattern=filename_pattern)
        self.logger.info(f"Model '{model_id}' successfully downloaded.")
        return target_path

    def load_model(
        self,
        model_id: str,
        engine_override: Optional[str] = None,
        quantization: Optional[str] = None,
        context_limit: Optional[int] = None,
        precision: Optional[str] = None,
        gpu_memory_utilization: Optional[float] = None,
    ) -> BaseInferenceEngine:
        """Downloads, validates, and loads a model into memory.

        Args:
            model_id: Model repository or file identifier.
            engine_override: Override engine name (e.g., 'transformers').
            quantization: Quantization type override.
            context_limit: Context length limit override.
            precision: Data precision (float16, bfloat16, float32).
            gpu_memory_utilization: VRAM usage limit (0.0 to 1.0).

        Returns:
            BaseInferenceEngine: The active inference engine loaded with the model.
        """
        if self.active_model_id == model_id and self.active_engine is not None:
            self.logger.info(f"Model '{model_id}' is already loaded.")
            return self.active_engine

        # Retrieve profile for default configuration mapping
        # Extract family name from model ID (e.g. Qwen/Qwen2.5-1.5B -> Qwen)
        family = model_id.split("/")[0] if "/" in model_id else "custom"
        profile = get_profile(family)

        # Merge defaults
        selected_engine = engine_override or profile.preferred_engine
        selected_ctx = context_limit or profile.context_limit
        selected_quant = quantization or "none"
        selected_gpu_util = gpu_memory_utilization or profile.recommended_gpu_utilization

        self.logger.info(f"Loading '{model_id}' using profile '{profile.name}' on engine '{selected_engine}'...")

        # 1. Download if missing (Assume GGUF suffix signals single file GGUF download)
        is_gguf = model_id.endswith(".gguf") or selected_engine == "llama.cpp"
        
        pattern = "*.gguf" if is_gguf else None
        local_path = self.download_model(model_id, filename_pattern=pattern)

        # If a single GGUF file is selected, determine the exact path of that file
        if is_gguf:
            gguf_files = list(local_path.glob("*.gguf"))
            if not gguf_files:
                raise ModelNotFoundError(model_id, log_info={"details": "No GGUF file found in cache path."})
            load_path = str(gguf_files[0])
        else:
            load_path = str(local_path)

        # 2. Instantiate and load Inference Engine
        engine_config = {
            "model_id": model_id,
            "quantization": selected_quant,
            "context_limit": selected_ctx,
            "precision": precision or "float16",
            "gpu_memory_utilization": selected_gpu_util,
        }

        # Safe switch logic: unload active engine first to prevent double-memory allocations
        self.unload_model()

        try:
            engine = get_engine(selected_engine, engine_config)
            engine.load_model(load_path, parameters=engine_config)

            self.active_engine = engine
            self.active_model_id = model_id
            self.logger.info(f"Model '{model_id}' successfully loaded.")
            return engine
        except Exception as e:
            self.logger.error(f"Failed to load model '{model_id}': {e}", exc_info=True)
            self.unload_model()
            raise e

    def unload_model(self) -> None:
        """Safely unloads the active model and releases all engine assets."""
        if self.active_engine:
            self.logger.info(f"Unloading active model '{self.active_model_id}'...")
            try:
                self.active_engine.unload_model()
            except Exception as e:
                self.logger.warning(f"Error while unloading engine: {e}")
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
