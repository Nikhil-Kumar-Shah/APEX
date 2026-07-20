"""Unified API configuration."""

from dataclasses import dataclass
from typing import Optional

@dataclass
class APIConfig:
    """Single source of truth for API configuration."""
    api_enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    openai_compatible: bool = True
    enable_auth: bool = False
    api_key: Optional[str] = None
    auto_generate_key: bool = True
    enable_tunnel: bool = False
    tunnel_provider: str = "cloudflare"
    enable_request_logs: bool = True
    enable_queue: bool = True
    max_concurrent_requests: int = 1
    cors_mode: str = "developer"  # "developer", "restricted", "disabled"
    show_public_url: bool = True
