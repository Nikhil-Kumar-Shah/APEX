"""Validation framework for the runtime."""

import importlib.util
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class ValidationError(Exception):
    """Exception raised for validation failures."""

    pass


class Validator:
    """Base class for validators."""

    @staticmethod
    def validate_path(path: Path, should_exist: bool = False, check_writable: bool = False) -> None:
        """Validates standard path requirements.

        Args:
            path: The file or directory path.
            should_exist: If True, raises error if path doesn't exist.
            check_writable: If True, raises error if path or parent is not writable.
        """
        if should_exist and not path.exists():
            raise ValidationError(f"Path does not exist: {path}")

        if check_writable:
            # If path exists, check if it's writeable. Otherwise check if parent is writeable.
            target = path if path.exists() else path.parent
            if target.exists() and not os.access(target, os.W_OK):
                raise ValidationError(f"Path is not writable: {path}")


class ConfigValidator(Validator):
    """Validates the configuration structure and types."""

    REQUIRED_KEYS = {
        "project_id": str,
        "project_name": str,
        "runtime_version": str,
        "config_version": str,
    }

    @classmethod
    def validate(cls, config: Dict[str, Any]) -> None:
        """Validates configuration keys, types, and values.

        Args:
            config: Configuration dictionary.
        """
        if not isinstance(config, dict):
            raise ValidationError("Configuration must be a dictionary.")

        # Check required fields
        for key, expected_type in cls.REQUIRED_KEYS.items():
            if key not in config:
                raise ValidationError(f"Missing required configuration key: '{key}'")
            if not isinstance(config[key], expected_type):
                raise ValidationError(
                    f"Configuration key '{key}' must be of type {expected_type.__name__}, got {type(config[key]).__name__}"
                )

        # Validate project ID format (slug)
        project_id = config["project_id"]
        if not re.match(r"^[a-z0-9\-_]+$", project_id):
            raise ValidationError(
                f"Invalid project_id '{project_id}'. It must contain only lowercase letters, numbers, hyphens, and underscores."
            )

        # Validate version formats
        for ver_key in ["runtime_version", "config_version"]:
            val = config[ver_key]
            if not re.match(r"^\d+\.\d+\.\d+$", val):
                raise ValidationError(
                    f"Invalid format for '{ver_key}': '{val}'. Must follow semantic versioning (e.g. 1.0.0)."
                )


class DependencyValidator(Validator):
    """Validates presence and version compatibility of python dependencies."""

    @staticmethod
    def validate_dependency(package_name: str) -> None:
        """Checks if a python package is installed.

        Args:
            package_name: Package name.
        """
        spec = importlib.util.find_spec(package_name)
        if spec is None:
            raise ValidationError(f"Required python dependency is missing: {package_name}")


class EnvironmentValidator(Validator):
    """Validates overall system environment prerequisites."""

    @classmethod
    def validate(cls, required_dirs: List[Path]) -> None:
        """Checks path access and system prerequisites.

        Args:
            required_dirs: Directories that must be writable.
        """
        for directory in required_dirs:
            cls.validate_path(directory, check_writable=True)
