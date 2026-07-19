"""Model cache manager for cached weights and configurations."""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


class CacheManager:
    """Manages the local cache directories for downloaded LLMs."""

    def __init__(self, cache_dir: Path):
        """Initializes the CacheManager.

        Args:
            cache_dir: Base directory for the model cache.
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_model_cache_path(self, model_id: str) -> Path:
        """Determines the local directory path for a specific model ID.

        Normalizes Hugging Face repo IDs to valid directory slugs.

        Args:
            model_id: The model identifier (e.g., 'Qwen/Qwen2.5-1.5B-Instruct').

        Returns:
            Path: The normalized local directory path.
        """
        normalized_id = model_id.replace("/", "--")
        return self.cache_dir / normalized_id

    def is_cached(self, model_id: str) -> bool:
        """Checks if a model is fully cached locally.

        For GGUF, looks for a single .gguf file. For PyTorch/Safetensors,
        checks if standard files (e.g., config.json and weight files) are present.

        Args:
            model_id: The model identifier.

        Returns:
            bool: True if cached files exist.
        """
        path = self.get_model_cache_path(model_id)
        if not path.is_dir():
            return False

        # If it's a GGUF format, check for at least one GGUF file
        gguf_files = list(path.glob("*.gguf"))
        if gguf_files:
            return True

        # Otherwise check for config.json (representing HuggingFace model structures)
        if (path / "config.json").exists():
            # Check that there is at least one safetensors or pytorch bin file
            weights = list(path.glob("*.safetensors")) + list(path.glob("*.bin"))
            if weights:
                return True

        return False

    def get_cache_size_bytes(self, model_id: Optional[str] = None) -> int:
        """Calculates total bytes occupied by cached models.

        Args:
            model_id: Optional model ID to compute size for. If None, computes total size.

        Returns:
            int: Size in bytes.
        """
        target_dir = self.get_model_cache_path(model_id) if model_id else self.cache_dir
        if not target_dir.exists():
            return 0

        total_size = 0
        for p in target_dir.rglob("*"):
            if p.is_file():
                try:
                    total_size += p.stat().st_size
                except OSError:
                    pass
        return total_size

    def list_cached_models(self) -> List[Dict[str, Any]]:
        """Lists metadata about all models currently residing in the cache.

        Returns:
            List[Dict[str, Any]]: List of dictionary metadata records.
        """
        models = []

        if not self.cache_dir.exists():
            return models

        for child in self.cache_dir.iterdir():
            if child.is_dir():
                # Reconstruct HuggingFace Model ID format from directory name
                name = child.name.replace("--", "/")
                size_bytes = self.get_cache_size_bytes(name)
                models.append(
                    {
                        "model_id": name,
                        "path": str(child),
                        "size_gb": size_bytes / (1024**3),
                        "fully_cached": self.is_cached(name),
                    }
                )
        return models

    def remove_model(self, model_id: str) -> bool:
        """Purges a model from the local cache storage.

        Args:
            model_id: The model identifier.

        Returns:
            bool: True if deleted successfully.
        """
        path = self.get_model_cache_path(model_id)
        if path.is_dir():
            try:
                shutil.rmtree(path)
                return True
            except OSError:
                return False
        return False
