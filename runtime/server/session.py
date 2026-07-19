"""Session tracking and timeout management."""

import uuid
import time
from typing import Any, Dict, Optional


class SessionManager:
    """Manages active request sessions and handles timeout state cleanups."""

    def __init__(self, session_timeout_seconds: float = 600.0):
        self.session_timeout = session_timeout_seconds
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Creates a new unique session identifier and registers it.

        Args:
            metadata: Custom dictionary metadata to attach to the session.

        Returns:
            str: Generated session ID string.
        """
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "id": session_id,
            "created_at": time.time(),
            "last_accessed_at": time.time(),
            "metadata": metadata or {},
        }
        return session_id

    def is_session_active(self, session_id: str) -> bool:
        """Checks if a session is currently active and not timed out.

        Args:
            session_id: Session identifier.

        Returns:
            bool: True if active, False if expired or non-existent.
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        # Check timeout
        if time.time() - session["last_accessed_at"] > self.session_timeout:
            self.close_session(session_id)
            return False

        # Touch last accessed
        session["last_accessed_at"] = time.time()
        return True

    def close_session(self, session_id: str) -> None:
        """Deregisters and cleans up a session.

        Args:
            session_id: Session identifier.
        """
        self.sessions.pop(session_id, None)

    def cleanup_expired_sessions(self) -> int:
        """Removes sessions that exceeded idle timeout bounds.

        Returns:
            int: Number of closed sessions.
        """
        now = time.time()
        expired_ids = [
            sid for sid, s in self.sessions.items()
            if now - s["last_accessed_at"] > self.session_timeout
        ]
        for sid in expired_ids:
            self.close_session(sid)
        return len(expired_ids)
