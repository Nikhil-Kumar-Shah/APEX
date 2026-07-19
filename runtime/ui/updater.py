"""Version checking and runtime update notifications."""

from typing import Any, Dict


class UpdateChecker:
    """Checks runtime version parameters and notifies users of compatible upgrades."""

    LATEST_RUNTIME_VERSION = "1.0.0"
    LATEST_CONFIG_VERSION = "1.0.0"


    def __init__(self, current_runtime_version: str, current_config_version: str):
        """Initializes the UpdateChecker.

        Args:
            current_runtime_version: Current version of the python package.
            current_config_version: Current version of configuration schemas.
        """
        self.current_runtime_version = current_runtime_version
        self.current_config_version = current_config_version

    def check_for_updates(self) -> Dict[str, Any]:
        """Compares current versions with latest repository release targets.

        Returns:
            Dict[str, Any]: Dictionary detailing update availability.
        """
        runtime_update = self._is_newer(self.LATEST_RUNTIME_VERSION, self.current_runtime_version)
        config_update = self._is_newer(self.LATEST_CONFIG_VERSION, self.current_config_version)

        update_available = runtime_update or config_update
        message = ""
        if update_available:
            msg_parts = []
            if runtime_update:
                msg_parts.append(f"Runtime package update available (Latest: {self.LATEST_RUNTIME_VERSION})")
            if config_update:
                msg_parts.append(f"Configuration schema migration available (Latest: {self.LATEST_CONFIG_VERSION})")
            message = " & ".join(msg_parts) + ". Update recommended."
        else:
            message = "APEX is up to date."

        return {
            "update_available": update_available,
            "runtime_update_available": runtime_update,
            "config_update_available": config_update,
            "message": message,
        }

    def _is_newer(self, latest: str, current: str) -> bool:
        try:
            latest_parts = [int(p) for p in latest.split(".")]
            current_parts = [int(p) for p in current.split(".")]
            return latest_parts > current_parts
        except (ValueError, AttributeError):
            return False
