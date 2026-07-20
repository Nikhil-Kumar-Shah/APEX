"""State machine tracking runtime statuses and transitions."""

import logging
from typing import List, Optional

logger = logging.getLogger("runtime.orchestrator.state")


class RuntimeStateMachine:
    """Manages the lifecycle state of the APEX runtime engine and safeguards transitions."""

    STATES = [
        "STOPPED",
        "INITIALIZING",
        "CHECKING_DEPENDENCIES",
        "INSTALLING_DEPENDENCIES",
        "DETECTING_HARDWARE",
        "DETECTING_ENGINES",
        "DOWNLOADING_MODEL",
        "VERIFYING_MODEL",
        "LOADING_MODEL",
        "GPU_WARMUP",
        "READY",
        "RUNNING",
        "UNLOADING",
        "STOPPING",
        "FAILED",
    ]

    def __init__(self, initial_state: str = "STOPPED"):
        """Initializes the RuntimeStateMachine."""
        self._state = initial_state if initial_state in self.STATES else "STOPPED"
        self.listeners = []

    @property
    def current_state(self) -> str:
        """Gets the active runtime state."""
        return self._state

    def transition_to(self, new_state: str) -> bool:
        """Transition system status to the new state.

        Args:
            new_state: Target state string.

        Returns:
            bool: True if transition was successfully set.
        """
        if new_state not in self.STATES:
            logger.error(f"Invalid target state: {new_state}", extra={"prefix": "ERROR"})
            return False

        old_state = self._state
        self._state = new_state
        logger.info(f"Transitioned {old_state} -> {new_state}", extra={"prefix": "SYSTEM"})
        
        # Trigger callbacks
        for listener in self.listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:
                logger.warning(f"Error executing state listener: {e}")
        return True

    def register_listener(self, callback) -> None:
        """Registers a callback to execute on status transitions."""
        self.listeners.append(callback)
