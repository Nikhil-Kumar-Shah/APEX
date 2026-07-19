"""Event dispatcher implementing Publish-Subscribe design patterns."""

import logging
from typing import Callable, Dict, List
from runtime.orchestrator.events import RuntimeEvent

logger = logging.getLogger("runtime.orchestrator.dispatcher")


class EventDispatcher:
    """Manages subscription registers and broadcasts events across the runtime."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable[[RuntimeEvent], None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[RuntimeEvent], None]) -> None:
        """Registers a callback for a specific event type.

        Args:
            event_type: Name of event to watch.
            callback: Function to run.
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def publish(self, event: RuntimeEvent) -> None:
        """Broadcasts an event to all subscribed listeners.

        Args:
            event: Event payload package.
        """
        listeners = self._listeners.get(event.event_type, [])
        for listener in listeners:
            try:
                listener(event)
            except Exception as e:
                logger.warning(f"Failed to execute listener callback: {e}")

        # Broad wildcard listener support
        wildcard_listeners = self._listeners.get("*", [])
        for listener in wildcard_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.warning(f"Failed to execute wildcard listener: {e}")
