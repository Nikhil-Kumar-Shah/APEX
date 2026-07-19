"""Notification registry managing alerts history."""

import time
from typing import Any, Dict, List


class NotificationCenter:
    """Stores user notices, warning messages, and task completion records."""

    def __init__(self, history_limit: int = 50):
        self.history_limit = history_limit
        self.notifications: List[Dict[str, Any]] = []

    def notify(self, message: str, level: str = "info") -> None:
        """Appends a new notification alert.

        Args:
            message: Text summary.
            level: info, success, warning, or error.
        """
        self.notifications.append({
            "message": message,
            "level": level.lower().strip(),
            "timestamp": time.time(),
            "read": False
        })
        if len(self.notifications) > self.history_limit:
            self.notifications.pop(0)

    def get_unread(self) -> List[Dict[str, Any]]:
        """Returns all unread notifications."""
        return [n for n in self.notifications if not n["read"]]

    def mark_all_read(self) -> None:
        """Flags all active alerts as read."""
        for n in self.notifications:
            n["read"] = True
