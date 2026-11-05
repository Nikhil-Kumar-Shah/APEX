"""Model cache manager for cached weights and configurations."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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
        """Checks if a model is fully and validly cached locally.

        Verifies:
        1. Model directory exists.
        2. No temporary or incomplete download files are present (.incomplete, .tmp, .part).
        3. Config exists, is non-empty, and parses as valid JSON.
        4. Weight files exist and have non-zero size.

        Args:
            model_id: The model identifier.

        Returns:
            bool: True if verified cached files exist without corruption.
        """
        path = self.get_model_cache_path(model_id)
        if not path.is_dir():
            return False

        # Incomplete download detection
        for item in path.glob("*"):
            if item.suffix in [".incomplete", ".tmp", ".part", ".download"]:
                return False

        # Check for GGUF format
        gguf_files = [f for f in path.glob("*.gguf") if f.is_file() and f.stat().st_size > 0]
        if gguf_files:
            return True

        # Check for config.json (HuggingFace structure)
        config_path = path / "config.json"
        if not config_path.is_file() or config_path.stat().st_size == 0:
            return False

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                if not isinstance(config_data, dict):
                    return False
        except Exception:
            return False

        # Verify weights exist and have size > 0
        weights = [
            f for f in (list(path.glob("*.safetensors")) + list(path.glob("*.bin")))
            if f.is_file() and f.stat().st_size > 0
        ]
        if not weights:
            return False

        return True

    def verify_cache_integrity(self, model_id: str) -> Tuple[bool, str]:
        """Performs a detailed integrity check on the cached model.

        Returns:
            Tuple[bool, str]: (is_valid, reason_if_invalid)
        """
        path = self.get_model_cache_path(model_id)
        if not path.is_dir():
            return False, f"Model cache directory does not exist: {path}"

        # Incomplete files
        incompletes = list(path.glob("*.incomplete")) + list(path.glob("*.tmp"))
        if incompletes:
            return False, f"Found {len(incompletes)} incomplete download artifacts."

        # Config check
        config_path = path / "config.json"
        if not config_path.is_file():
            return False, "Missing config.json."
        if config_path.stat().st_size == 0:
            return False, "config.json is 0 bytes."
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                json.load(f)
        except Exception as e:
            return False, f"config.json is corrupted: {e}"

        # Weights check
        weights = [
            f for f in (list(path.glob("*.safetensors")) + list(path.glob("*.bin")) + list(path.glob("*.gguf")))
            if f.is_file() and f.stat().st_size > 0
        ]
        if not weights:
            return False, "No valid non-empty weight files found (.safetensors, .bin, or .gguf)."

        return True, "Cache integrity verified."

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
