from typing import Any, Callable

class ThemeManager:
    """Manages light and dark theme styling templates injection."""

    def __init__(self, initial_dark: bool = True):
        self.dark_mode = initial_dark
        self.listeners = []

    def set_theme(self, dark_mode: bool) -> None:
        """Sets the active theme and notifies all registered components.

        Args:
            dark_mode: True to use Dark Mode, False for Light Mode.
        """
        self.dark_mode = dark_mode
        for listener in self.listeners:
            try:
                listener(self.dark_mode)
            except Exception:
                pass

    def register_listener(self, callback: Callable[[bool], None]) -> None:
        """Registers a callback to execute on theme change events."""
        self.listeners.append(callback)
