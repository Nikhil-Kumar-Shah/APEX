"""Portability utilities for configuration import, export, and migration."""

import json
from pathlib import Path
from typing import Any, Dict

from runtime.config.manager import ConfigManager
from runtime.config.schema import DEFAULT_CONFIG_VERSION
from runtime.memory.errors import ConfigurationMismatchError, ExportFailedError, ImportFailedError
from runtime.validation.validators import ConfigValidator, ValidationError


class ConfigurationPortability:
    """Handles serializing, validating, importing, and exporting configuration states."""

    @staticmethod
    def export_config(config_manager: ConfigManager, export_path: Path) -> None:
        """Serializes and saves the active configuration to a portable file.

        Args:
            config_manager: The active ConfigManager.
            export_path: Destination file path.
        """
        try:
            config_data = config_manager.config
            if not config_data:
                config_data = config_manager.load()

            # Perform validation check before exporting
            ConfigValidator.validate(config_data)

            export_path.parent.mkdir(parents=True, exist_ok=True)
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
        except ValidationError as ve:
            raise ExportFailedError(str(export_path), f"Validation failed: {ve}")
        except OSError as oe:
            raise ExportFailedError(str(export_path), f"IO error: {oe}")

    @staticmethod
    def import_config(config_manager: ConfigManager, import_path: Path) -> None:
        """Imports and validates configuration settings from a portable file.

        Args:
            config_manager: Target ConfigManager to write settings into.
            import_path: Source file path.
        """
        if not import_path.is_file():
            raise ImportFailedError(str(import_path), "Import file does not exist.")

        try:
            with open(import_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate imported structure matches expected schemas
            ConfigValidator.validate(data)

            # Version check
            config_ver = data.get("config_version", "0.0.0")
            if config_ver != DEFAULT_CONFIG_VERSION:
                # Perform migration using ConfigManager's internal migration
                data = config_manager._migrate(data)

            success = config_manager.save(data)
            if not success:
                raise ImportFailedError(str(import_path), "Failed to save configuration via manager.")
        except json.JSONDecodeError as je:
            raise ImportFailedError(str(import_path), f"Invalid JSON format: {je}")
        except ValidationError as ve:
            raise ImportFailedError(str(import_path), f"Schema validation failed: {ve}")
        except OSError as oe:
            raise ImportFailedError(str(import_path), f"IO error: {oe}")
