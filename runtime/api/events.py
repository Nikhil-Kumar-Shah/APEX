"""Runtime events for tracking API requests."""

import logging
from enum import Enum
from typing import Any, Dict

logger = logging.getLogger("apex.events")

class EventType(str, Enum):
    REQUEST_CREATED = "Request Created"
    VALIDATED = "Validated"
    QUEUED = "Queued"
    STARTED = "Started"
    RUNNING = "Running"
    STREAMING = "Streaming"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    FAILED = "Failed"

def emit_event(event_type: EventType, request_id: str, payload: Dict[str, Any] = None):
    """Emit a runtime event for a request."""
    logger.info(f"[{request_id}] {event_type.value} - {payload or {}}")
