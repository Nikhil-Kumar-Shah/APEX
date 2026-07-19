"""Central memory coordinator managing workspaces, projects, conversations, and indexes."""

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.utils.file import safe_read_json, safe_write_json
from runtime.memory.errors import SessionRestoreFailedError
from runtime.memory.workspace import WorkspaceManager
from runtime.memory.conversation import ConversationMemoryManager
from runtime.memory.project import ProjectMemory
from runtime.memory.repository import RepositoryIndexer
from runtime.memory.portability import ConfigurationPortability
from runtime.memory.cleanup import MemoryCleanupManager

logger = logging.getLogger("runtime.memory")


class MemoryManager:
    """Central orchestrator for all persistent states, metadata indexes, and workspace backups."""

    def __init__(self, storage_root: Path, cache_root: Path):
        """Initializes the MemoryManager.

        Args:
            storage_root: Core directory for persistent storage (e.g. workspaces, session keys).
            cache_root: Base cache folder for weights and temporary assets.
        """
        self.storage_root = storage_root
        self.cache_root = cache_root

        # Initialize sub-managers
        self.workspaces_dir = storage_root / "workspaces"
        self.workspace_mgr = WorkspaceManager(self.workspaces_dir)
        
        # Default workspace initialization
        self.workspace_mgr.load_workspace("default")

        # Initialize domain-specific managers mapped to the default workspace path
        self.convo_mgr = ConversationMemoryManager(self.workspace_mgr.active_workspace_path)
        self.project_mem = ProjectMemory(self.workspace_mgr.active_workspace_path)
        self.repo_indexer = RepositoryIndexer(self.workspace_mgr.active_workspace_path)
        self.portability = ConfigurationPortability()
        self.cleanup_mgr = MemoryCleanupManager(self.workspaces_dir, cache_root)

    def switch_workspace(self, workspace_id: str) -> None:
        """Safely transitions to a different workspace partition.

        Args:
            workspace_id: Unique string slug ID.
        """
        logger.info(f"Switching active memory workspace to '{workspace_id}'...")
        self.workspace_mgr.load_workspace(workspace_id)
        
        # Re-initialize workspace specific sub-managers to active paths
        self.convo_mgr = ConversationMemoryManager(self.workspace_mgr.active_workspace_path)
        self.project_mem = ProjectMemory(self.workspace_mgr.active_workspace_path)
        self.repo_indexer = RepositoryIndexer(self.workspace_mgr.active_workspace_path)

    @property
    def session_filepath(self) -> Path:
        """Determines path to the session backup file."""
        return self.storage_root / "session.json"

    def save_session_state(self, active_model_id: Optional[str] = None, active_project_id: Optional[str] = None) -> None:
        """Saves current runtime session to disk to allow restoration later.

        Args:
            active_model_id: Currently loaded model.
            active_project_id: Currently loaded project ID.
        """
        session_data = {
            "active_workspace_id": self.workspace_mgr.active_workspace_id,
            "active_project_id": active_project_id,
            "active_model_id": active_model_id,
            "timestamp": time.time(),
        }
        safe_write_json(self.session_filepath, session_data)
        logger.info("[+] Session state saved successfully.")

    def restore_session_state(self) -> Dict[str, Any]:
        """Loads and restores the last active session parameters.

        Returns:
            Dict[str, Any]: Dictionary containing active workspace, project, and model IDs.
        """
        if not self.session_filepath.is_file():
            return {
                "active_workspace_id": "default",
                "active_project_id": None,
                "active_model_id": None,
            }

        data = safe_read_json(self.session_filepath)
        if not data:
            raise SessionRestoreFailedError("unknown", "Session data file is corrupted or unreadable.")

        # Switch to last active workspace
        last_ws = data.get("active_workspace_id", "default")
        try:
            self.switch_workspace(last_ws)
        except Exception as e:
            raise SessionRestoreFailedError(last_ws, f"Could not mount workspace: {e}")

        logger.info(f"[+] Restored workspace '{last_ws}' from session backup.")
        return {
            "active_workspace_id": last_ws,
            "active_project_id": data.get("active_project_id"),
            "active_model_id": data.get("active_model_id"),
        }

    def backup_workspace(self, workspace_id: str, backup_dest: Path) -> Path:
        """Creates a zipped archive backup of a workspace folder.

        Args:
            workspace_id: Slug ID.
            backup_dest: Target folder path.

        Returns:
            Path: Zipped file path.
        """
        ws_path = self.workspaces_dir / workspace_id
        if not ws_path.is_dir():
            raise FileNotFoundError(f"Workspace {workspace_id} does not exist.")

        backup_dest.mkdir(parents=True, exist_ok=True)
        archive_name = backup_dest / f"backup_{workspace_id}_{int(time.time())}"
        
        # Create zip archive using shutil
        archive_filepath = shutil.make_archive(
            base_name=str(archive_name),
            format="zip",
            root_dir=str(ws_path),
        )
        logger.info(f"[+] Workspace '{workspace_id}' archived at: {archive_filepath}")
        return Path(archive_filepath)

    def restore_workspace_from_backup(self, workspace_id: str, backup_archive: Path) -> None:
        """Restores a workspace directory from a zip archive.

        Args:
            workspace_id: Target workspace ID to restore into.
            backup_archive: Path to the zip backup.
        """
        if not backup_archive.is_file():
            raise FileNotFoundError(f"Backup archive {backup_archive} does not exist.")

        target_path = self.workspaces_dir / workspace_id
        
        # Safe clear target if existing
        if target_path.exists():
            shutil.rmtree(target_path)
            
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Unzip
        shutil.unpack_archive(str(backup_archive), extract_dir=str(target_path), format="zip")
        logger.info(f"[+] Workspace '{workspace_id}' restored from backup: {backup_archive}")
        
        # Force refresh active pointers if restoring current active workspace
        if workspace_id == self.workspace_mgr.active_workspace_id:
            self.switch_workspace(workspace_id)
