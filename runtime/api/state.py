"""Central Runtime State for API, Notebook, and Dashboard."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional


class APIStatus(str, Enum):
    """Lifecycle states of the API server — never assume RUNNING without verification."""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    VERIFYING = "VERIFYING"
    RUNNING = "RUNNING"
    FAILED = "FAILED"


@dataclass
class RuntimeState:
    """
    Single source of truth for the full runtime state.
    Dashboard, Notebook, and API all read from this object.
    Nothing is ever assumed — every field reflects a verified real state.
    """
    # API Server
    api_status: APIStatus = APIStatus.STOPPED
    host: str = "0.0.0.0"
    port: int = 8000
    pid: Optional[int] = None

    # Authentication
    authentication: str = "Disabled"
    api_key: Optional[str] = None

    # Tunnel
    tunnel_connected: bool = False
    public_url: Optional[str] = None
    openai_url: Optional[str] = None

    # Environment
    is_colab: bool = False

    # Model
    model_loaded: Optional[str] = None

    # Telemetry
    queue_size: int = 0
    total_requests: int = 0
    total_tokens: int = 0
    worker_alive: bool = False

    # Health
    health_checked: bool = False
    last_health_ms: Optional[float] = None

    # Errors
    last_error: Optional[str] = None
    errors: List[str] = field(default_factory=list)

    # GPU
    gpu_stats: Dict[str, Any] = field(default_factory=dict)

    # Workspace
    workspace: str = "default"

    @property
    def api_running(self) -> bool:
        """Backwards-compatible property — True only if verified RUNNING."""
        return self.api_status == APIStatus.RUNNING
