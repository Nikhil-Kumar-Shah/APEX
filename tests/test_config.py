"""Unit tests for configuration management."""

import pytest
from pathlib import Path
from runtime.config.manager import ConfigManager
from runtime.config.schema import DEFAULT_CONFIG_TEMPLATE
from runtime.validation.validators import ValidationError


def test_config_load_default(tmp_path: Path):
    """Tests loading configuration from a missing file defaults properly."""
    config_file = tmp_path / "missing_config.json"
    manager = ConfigManager(config_file)

    loaded = manager.load()
    assert loaded["project_id"] == DEFAULT_CONFIG_TEMPLATE["project_id"]
    assert loaded["project_name"] == DEFAULT_CONFIG_TEMPLATE["project_name"]


def test_config_save_and_load(tmp_path: Path):
    """Tests saving configurations and re-loading them back."""
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_file)

    custom_config = DEFAULT_CONFIG_TEMPLATE.copy()
    custom_config["project_id"] = "my-custom-project"
    custom_config["project_name"] = "My Custom Project"

    # Save
    assert manager.save(custom_config)
    assert config_file.exists()

    # Load from another manager
    new_manager = ConfigManager(config_file)
    loaded = new_manager.load()
    assert loaded["project_id"] == "my-custom-project"
    assert loaded["project_name"] == "My Custom Project"


def test_config_save_validation_failure(tmp_path: Path):
    """Tests saving configurations with invalid schema structures fails."""
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_file)

    bad_config = DEFAULT_CONFIG_TEMPLATE.copy()
    bad_config["project_id"] = "Invalid Project ID with Spaces"

    with pytest.raises(ValidationError):
        manager.save(bad_config)


def test_config_migration(tmp_path: Path):
    """Tests migrating older configuration version formats to the newest schema version."""
    config_file = tmp_path / "legacy_config.json"

    # Save legacy config manually without validation check
    legacy_data = {
        "project_id": "legacy-id",
        "project_name": "Legacy Name",
        "runtime_version": "0.1.0",
        "config_version": "0.9.0",  # older version
        # directories and logging fields are missing
    }

    import json
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(legacy_data, f)

    manager = ConfigManager(config_file)
    loaded = manager.load()

    # Check migrated values
    assert loaded["config_version"] == "1.0.0"
    assert loaded["project_id"] == "legacy-id"
    assert loaded["project_name"] == "Legacy Name"
    # Ensure nested dictionary values were filled from default template
    assert "directories" in loaded
    assert loaded["directories"]["cache_dir"] == "cache"
