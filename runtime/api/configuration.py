"""Unified API configuration."""

from dataclasses import dataclass
from typing import Optional

@dataclass
class APIConfig:
    """Single source of truth for API configuration."""
    api_enabled: bool = True
    transport: str = "cloudflare"  # "local", "cloudflare", "ngrok", "localtunnel"
    
    openai_compatible: bool = True
    enable_auth: bool = False
    api_key: Optional[str] = None
    auto_generate_key: bool = True
    
    # Internal runtime details (auto-managed)
    public_url: Optional[str] = None
    internal_host: str = "127.0.0.1"
    internal_port: Optional[int] = None
    enable_request_logs: bool = True
    enable_queue: bool = True
    max_concurrent_requests: int = 1
    cors_mode: str = "developer"  # "developer", "restricted", "disabled"
    show_public_url: bool = True
