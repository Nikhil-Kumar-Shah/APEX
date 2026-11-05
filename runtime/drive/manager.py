"""Google Drive integration and path management."""

import os
import sys
import threading
from pathlib import Path
from typing import Optional

from runtime.utils.env import is_colab


class DriveManager:
    """Manages file storage paths across Google Colab (Google Drive) and local systems."""

    def __init__(self, fallback_local_root: Optional[Path] = None):
        """Initializes DriveManager.

        Args:
            fallback_local_root: Path to use when not running in Colab (defaults to workspace root).
        """
        self.is_colab_env = is_colab()
        if fallback_local_root:
            self._local_root = fallback_local_root.resolve()
        else:
            # Resolve to the repository root directory
            self._local_root = Path(__file__).resolve().parent.parent.parent

        self.mount_point = Path("/content/drive")
        self._persistence_root: Optional[Path] = None

    def is_drive_mounted(self) -> bool:
        """Checks if Google Drive is already mounted and accessible.

        Returns:
            bool: True if mount_point and MyDrive subdirectory exist.
        """
        my_drive = self.mount_point / "MyDrive"
        return self.mount_point.exists() and my_drive.exists()

    def mount(self) -> bool:
        """Mounts Google Drive if running in Google Colab.

        Reuses an existing mount if already available to avoid blocking daemon
        threads or prompting for confirmation repeatedly.

        Returns:
            bool: True if mounted successfully or if running locally, False on failure.
        """
        if not self.is_colab_env:
            # Local environment mock mount
            self._persistence_root = self._local_root
            return True

        # Check if already mounted in the runtime
        if self.is_drive_mounted():
            try:
                self._persistence_root = self.mount_point / "MyDrive" / "APEX"
                self._persistence_root.mkdir(parents=True, exist_ok=True)
                return True
            except Exception:
                self._persistence_root = self._local_root
                return False

        # In a background worker thread, do NOT attempt interactive drive.mount()
        # because Google Colab cannot attach authorization prompts to background threads,
        # which blocks the thread for ~5 minutes until Colab's client timeout expires.
        if threading.current_thread() is not threading.main_thread():
            self._persistence_root = self._local_root
            return False

        try:
            # Dynamically import and run colab drive mount without force_remount
            from google.colab import drive

            drive.mount(str(self.mount_point))
            self._persistence_root = self.mount_point / "MyDrive" / "APEX"
            self._persistence_root.mkdir(parents=True, exist_ok=True)

            return True
        except Exception:
            self._persistence_root = self._local_root
            return False

    @property
    def project_root(self) -> Path:
        """Retrieves the project runtime root path (always local).

        Returns:
            Path: Absolute path of the project root.
        """
        return self._local_root

    @property
    def persistence_root(self) -> Path:
        """Retrieves the persistent storage root path (Drive if available).

        Returns:
            Path: Absolute path of the persistent root.
        """
        if self._persistence_root is None:
            # Fallback if mount() was not called
            self._persistence_root = self._local_root
        return self._persistence_root

    def get_path(self, relative_path: str, persistent: bool = False) -> Path:
        """Resolves a relative path against the project or persistence root.

        Args:
            relative_path: Relative path string (e.g., 'workspaces/default/config.json').
            persistent: Whether to use the persistent drive root.

        Returns:
            Path: Resolved absolute path.
        """
        base = self.persistence_root if persistent else self.project_root
        return (base / relative_path).resolve()
