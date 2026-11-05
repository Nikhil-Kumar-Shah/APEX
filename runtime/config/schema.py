"""Configuration schemas and defaults for APEX."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

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
        "enabled_backends": ["mock", "transformers"],
        "default_backend": "transformers",
    },
    "model": {
        "model_id": "Qwen/Qwen2.5-0.5B",
        "precision": "float16",
        "hf_token": None,
        "revision": None,
    },
    "api": {
        "transport": "cloudflare",
        "port": None,
        "enable_auth": False,
        "api_key": None,
        "cors_mode": "developer",
        "max_concurrent_requests": 1,
    },
    "generation": {
        "max_tokens": 2048,
        "temperature": 0.7,
        "top_p": 0.9,
    },
}


@dataclass
class ApexConfig:
    """Unified configuration object bridging UI, ModelManager, and APIManager."""

    # Project metadata
    project_id: str = "default-workspace"
    project_name: str = "Default Workspace"
    runtime_version: str = DEFAULT_RUNTIME_VERSION
    config_version: str = DEFAULT_CONFIG_VERSION

    # Model settings
    model_id: str = "Qwen/Qwen2.5-0.5B"
    precision: str = "float16"
    hf_token: Optional[str] = None
    revision: Optional[str] = None
    device: Optional[str] = None

    # API settings
    transport: str = "cloudflare"
    port: Optional[int] = None
    enable_auth: bool = False
    api_key: Optional[str] = None
    cors_mode: str = "developer"
    max_concurrent_requests: int = 1

    # Generation defaults
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9

    # Storage paths (relative or absolute)
    cache_dir: str = "cache"
    log_dir: str = "logs"
    output_dir: str = "outputs"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes into standard APEX schema dictionary."""
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "runtime_version": self.runtime_version,
            "config_version": self.config_version,
            "directories": {
                "cache_dir": self.cache_dir,
                "log_dir": self.log_dir,
                "output_dir": self.output_dir,
            },
            "logging": {
                "level": "INFO",
                "console": True,
                "file": True,
            },
            "inference": {
                "enabled_backends": ["transformers", "mock"],
                "default_backend": "transformers",
            },
            "model": {
                "model_id": self.model_id,
                "precision": self.precision,
                "hf_token": self.hf_token,
                "revision": self.revision,
                "device": self.device,
            },
            "api": {
                "transport": self.transport,
                "port": self.port,
                "enable_auth": self.enable_auth,
                "api_key": self.api_key,
                "cors_mode": self.cors_mode,
                "max_concurrent_requests": self.max_concurrent_requests,
            },
            "generation": {
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApexConfig":
        """Instantiates ApexConfig from dictionary, handling nested groups gracefully."""
        cfg = cls()
        cfg.project_id = data.get("project_id", cfg.project_id)
        cfg.project_name = data.get("project_name", cfg.project_name)
        cfg.runtime_version = data.get("runtime_version", cfg.runtime_version)
        cfg.config_version = data.get("config_version", cfg.config_version)

        # Model section
        model_sec = data.get("model", {})
        if isinstance(model_sec, dict):
            cfg.model_id = model_sec.get("model_id", data.get("model_id", cfg.model_id))
            cfg.precision = model_sec.get("precision", data.get("precision", cfg.precision))
            cfg.hf_token = model_sec.get("hf_token", cfg.hf_token)
            cfg.revision = model_sec.get("revision", cfg.revision)
            cfg.device = model_sec.get("device", data.get("device", cfg.device))

        # API section
        api_sec = data.get("api", {})
        if isinstance(api_sec, dict):
            cfg.transport = api_sec.get("transport", data.get("transport", cfg.transport))
            cfg.port = api_sec.get("port", data.get("port", cfg.port))
            cfg.enable_auth = api_sec.get("enable_auth", cfg.enable_auth)
            cfg.api_key = api_sec.get("api_key", cfg.api_key)
            cfg.cors_mode = api_sec.get("cors_mode", cfg.cors_mode)
            cfg.max_concurrent_requests = api_sec.get("max_concurrent_requests", cfg.max_concurrent_requests)

        # Generation section
        gen_sec = data.get("generation", {})
        if isinstance(gen_sec, dict):
            cfg.max_tokens = gen_sec.get("max_tokens", cfg.max_tokens)
            cfg.temperature = gen_sec.get("temperature", cfg.temperature)
            cfg.top_p = gen_sec.get("top_p", cfg.top_p)

        # Directories
        dirs_sec = data.get("directories", {})
        if isinstance(dirs_sec, dict):
            cfg.cache_dir = dirs_sec.get("cache_dir", cfg.cache_dir)
            cfg.log_dir = dirs_sec.get("log_dir", cfg.log_dir)
            cfg.output_dir = dirs_sec.get("output_dir", cfg.output_dir)

        return cfg
