"""System storage and memory cleanup utilities."""

import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List


class MemoryCleanupManager:
    """Manages files pruning, temp cache sweeps, and storage optimizations."""

    def __init__(self, workspace_root: Path, cache_root: Path):
        """Initializes the MemoryCleanupManager.

        Args:
            workspace_root: Path containing workspaces.
            cache_root: Path containing model caches.
        """
        self.workspace_root = workspace_root
        self.cache_root = cache_root

    def purge_temp_files(self, directory: Path) -> int:
        """Removes temporary files (.tmp suffix) from a directory tree.

        Args:
            directory: Path to scan.

        Returns:
            int: Number of files deleted.
        """
        deleted_count = 0
        if not directory.exists():
            return deleted_count

        for p in list(directory.rglob("*.tmp")):
            try:
                if p.is_file():
                    p.unlink()
                    deleted_count += 1
            except OSError:
                pass
        return deleted_count

    def clean_old_conversations(self, workspace_path: Path, max_age_days: float = 30.0) -> int:
        """Prunes conversation logs older than a specified duration.

        Args:
            workspace_path: Path to the active workspace.
            max_age_days: Retention window.

        Returns:
            int: Number of pruned logs.
        """
        deleted_count = 0
        convo_dir = workspace_path / "conversations"
        if not convo_dir.is_dir():
            return deleted_count

        max_age_seconds = max_age_days * 86400.0
        now = time.time()

        for child in convo_dir.glob("*.json"):
            try:
                stat = child.stat()
                # Use last modification time
                if now - stat.st_mtime > max_age_seconds:
                    child.unlink()
                    deleted_count += 1
            except OSError:
                pass
        return deleted_count

    def get_cleanup_stats(self) -> Dict[str, Any]:
        """Gathers diagnostic details for storage usage.

        Returns:
            Dict[str, Any]: Space measurements.
        """
        total_cache_size = 0
        if self.cache_root.exists():
            for p in self.cache_root.rglob("*"):
                if p.is_file():
                    try:
                        total_cache_size += p.stat().st_size
                    except OSError:
                        pass

        return {
            "cache_size_mb": total_cache_size / (1024**2),
            "workspaces_count": len(list(self.workspace_root.glob("*/workspace.json"))) if self.workspace_root.exists() else 0,
        }
