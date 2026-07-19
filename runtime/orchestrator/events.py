"""Event types and schemas for the event bus."""

import time
from typing import Any, Dict, Optional

class RuntimeEvent:
    """Represents a structured status or telemetry event emitted by the runtime."""

    def __init__(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """Initializes the RuntimeEvent.

        Args:
            event_type: String identifier (e.g. 'task_started', 'model_loaded').
            data: Data payload dictionaries.
        """
        self.event_type = event_type
        self.data = data or {}
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Converts the event to a JSON serializable dict.

        Returns:
            Dict[str, Any]: Compiled data parameters.
        """
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "data": self.data,
        }
