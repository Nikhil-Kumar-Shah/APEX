"""Configuration schemas and defaults for APEX."""

from typing import Any, Dict

# The current configuration schema version
DEFAULT_CONFIG_VERSION = "1.0.0"
DEFAULT_RUNTIME_VERSION = "1.0.0"

DEFAULT_CONFIG_TEMPLATE: Dict[str, Any] = {
    "project_id": "default-workspace",
    "project_name": "Default Workspace",
    "runtime_version": DEFAULT_RUNTIME_VERSION,
    "config_version": DEFAULT_CONFIG_VERSION,

    "directories": {
        "cache_dir": "cache",
        "log_dir": "logs",
        "output_dir": "outputs",
    },
    "logging": {
        "level": "INFO",
        "console": True,
        "file": True,
    },
    "inference": {
        "enabled_backends": ["mock"],
        "default_backend": "mock",
    },
}
