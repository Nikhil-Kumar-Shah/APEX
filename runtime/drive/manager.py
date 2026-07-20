"""Google Drive integration and path management."""

import os
import sys
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

    def mount(self) -> bool:
        """Mounts Google Drive if running in Google Colab.

        Returns:
            bool: True if mounted successfully or if running locally, False on failure.
        """
        if not self.is_colab_env:
            # Local environment mock mount
            self._persistence_root = self._local_root
            return True

        try:
            # Dynamically import and run colab drive mount
            from google.colab import drive

            drive.mount(str(self.mount_point), force_remount=True)
            # Typically, notebooks are stored in My Drive or a subfolder.
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
