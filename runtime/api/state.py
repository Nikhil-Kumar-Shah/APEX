"""Central Runtime State for API, Notebook, and Dashboard."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class RuntimeState:
    """Central state object."""
    api_running: bool = False
    authentication: str = "Disabled"
    api_key: Optional[str] = None
    tunnel_connected: bool = False
    public_url: Optional[str] = None
    model_loaded: Optional[str] = None
    queue_size: int = 0
    gpu_stats: Dict[str, Any] = field(default_factory=dict)
    workspace: str = "default"
    current_task: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    total_requests: int = 0
    total_tokens: int = 0
    worker_alive: bool = False
