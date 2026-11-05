"""Configuration Manager."""

from pathlib import Path
from typing import Any, Dict, Optional

from runtime.config.schema import DEFAULT_CONFIG_TEMPLATE, DEFAULT_CONFIG_VERSION, ApexConfig
from runtime.utils.file import safe_read_json, safe_write_json
from runtime.validation.validators import ConfigValidator, ValidationError


class ConfigManager:
    """Manages project configurations, migrations, and schema validation."""

    def __init__(self, config_path: Path):
        """Initializes the config manager.

        Args:
            config_path: File system path to the configuration JSON file.
        """
        self.config_path = config_path
        self._config: Dict[str, Any] = {}

    @property
    def config(self) -> Dict[str, Any]:
        """Returns the loaded configuration.

        Returns:
            Dict[str, Any]: The configuration dict.
        """
        return self._config

    def load(self) -> Dict[str, Any]:
        """Loads and validates configuration from the config file.

        Falls back to defaults if the file is missing or invalid.

        Returns:
            Dict[str, Any]: Loaded and validated configuration.
        """
        data = safe_read_json(self.config_path)

        if data is None:
            # Config file doesn't exist, use default template
            self._config = DEFAULT_CONFIG_TEMPLATE.copy()
        else:
            # Perform migration if needed
            self._config = self._migrate(data)

        # Validate loaded configuration
        try:
            ConfigValidator.validate(self._config)
        except ValidationError as e:
            # Log/Raise configuration corruption
            raise ValidationError(f"Configuration validation failed for {self.config_path}: {e}")

        return self._config

    def save(self, data: Optional[Dict[str, Any]] = None) -> bool:
        """Saves current configuration to the config path.

        Args:
            data: Optional new configuration dictionary. If None, saves self._config.

        Returns:
            bool: True if save succeeded.
        """
        config_to_save = data if data is not None else self._config

        # Always validate before writing
        ConfigValidator.validate(config_to_save)

        success = safe_write_json(self.config_path, config_to_save)
        if success and data is not None:
            self._config = data
        return success

    def get_apex_config(self) -> ApexConfig:
        """Returns the loaded configuration wrapped in an ApexConfig dataclass."""
        if not self._config:
            self.load()
        return ApexConfig.from_dict(self._config)

    def save_apex_config(self, apex_config: ApexConfig) -> bool:
        """Saves an ApexConfig object directly to the config file."""
        return self.save(apex_config.to_dict())

    def _migrate(self, old_config: Dict[str, Any]) -> Dict[str, Any]:
        """Migrates older configuration schemas to the current version.

        Args:
            old_config: The configuration loaded from file.

        Returns:
            Dict[str, Any]: The migrated/updated configuration.
        """
        current_version = old_config.get("config_version", "0.0.0")
        if current_version == DEFAULT_CONFIG_VERSION:
            return old_config

        # Copy defaults as baseline
        migrated = DEFAULT_CONFIG_TEMPLATE.copy()

        # Update baseline with all matching old keys (preserve modern version numbers)
        for key, val in old_config.items():
            if key in ("config_version", "runtime_version"):
                continue
            if key in migrated:
                if isinstance(migrated[key], dict) and isinstance(val, dict):
                    # Shallow merge nested dicts (like directories, logging, model, api)
                    merged = migrated[key].copy()
                    merged.update(val)
                    migrated[key] = merged
                else:
                    migrated[key] = val

        return migrated
