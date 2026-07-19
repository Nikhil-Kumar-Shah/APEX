"""Unit tests for ModelManager, caching, and downloading."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from runtime.config.profile import get_profile
from runtime.core.errors import ModelNotFoundError
from runtime.model.cache import CacheManager
from runtime.model.downloader import ModelDownloader
from runtime.model.manager import ModelManager


def test_model_profiles():
    """Validates that preset profiles retrieve matching limits and engines."""
    qwen = get_profile("qwen")
    assert qwen.name == "Qwen"
    assert qwen.preferred_engine == "vllm"
    assert qwen.context_limit == 32768

    custom = get_profile("some-unknown-family")
    assert custom.name == "Custom"
    assert custom.preferred_engine == "transformers"


def test_cache_manager(tmp_path: Path):
    """Validates CacheManager folder calculations and listings."""
    cache = CacheManager(tmp_path)
    model_id = "test/model-a"

    assert not cache.is_cached(model_id)
    assert cache.get_cache_size_bytes(model_id) == 0

    model_dir = cache.get_model_cache_path(model_id)
    model_dir.mkdir(parents=True)

    # Put a fake config.json and weight file to simulate cache presence
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_text("data", encoding="utf-8")

    assert cache.is_cached(model_id)
    assert cache.get_cache_size_bytes(model_id) > 0


    models = cache.list_cached_models()
    assert len(models) == 1
    assert models[0]["model_id"] == model_id

    # Delete
    assert cache.remove_model(model_id)
    assert not cache.is_cached(model_id)


@patch("runtime.model.downloader.ModelDownloader.download")
def test_model_manager_load(mock_download, tmp_path: Path):
    """Tests loading, caching check, and unloading via ModelManager."""
    manager = ModelManager(tmp_path)
    model_id = "test/model-b"

    # Make download a no-op returning target path
    mock_download.return_value = tmp_path / "test--model-b"

    # Write mock files to satisfy is_cached Check
    model_dir = tmp_path / "test--model-b"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_text("data", encoding="utf-8")

    # Load with mock engine
    engine = manager.load_model(model_id, engine_override="mock")
    assert manager.active_model_id == model_id
    assert engine.is_loaded

    # Check status report
    status = manager.get_status()
    assert status["active_model_id"] == model_id
    assert status["is_loaded"] is True
    assert status["engine_status"]["engine"] == "mock"

    # Unload
    manager.unload_model()
    assert manager.active_model_id is None
    assert manager.active_engine is None
