"""Workspace tracking and layout setup."""

import time
from pathlib import Path
from typing import Any, Dict, List

from runtime.utils.file import ensure_directory, safe_read_json, safe_write_json
from runtime.memory.errors import WorkspaceNotFoundError


class WorkspaceManager:
    """Manages the creation, switching, loading, and validation of independent workspace structures."""

    def __init__(self, workspaces_root: Path):
        """Initializes the WorkspaceManager.

        Args:
            workspaces_root: Directory where workspaces are partitioned.
        """
        self.workspaces_root = workspaces_root
        self.workspaces_root.mkdir(parents=True, exist_ok=True)
        self.active_workspace_id: str = "default"

    @property
    def active_workspace_path(self) -> Path:
        """Gets the path of the active workspace folder.

        Returns:
            Path: The active workspace directory.
        """
        return self.workspaces_root / self.active_workspace_id

    def create_workspace(self, workspace_id: str, name: str) -> Path:
        """Initializes a new workspace directory layout with folders for logs/memory.

        Args:
            workspace_id: Unique string slug ID.
            name: Human-friendly name.

        Returns:
            Path: Path to the initialized workspace root.
        """
        ws_path = self.workspaces_root / workspace_id
        ws_path.mkdir(parents=True, exist_ok=True)

        # Initialize standard subdirectories
        (ws_path / "conversations").mkdir(exist_ok=True)
        (ws_path / "projects").mkdir(exist_ok=True)
        (ws_path / "repositories").mkdir(exist_ok=True)

        # Write workspace manifest file
        manifest_path = ws_path / "workspace.json"
        manifest_data = {
            "workspace_id": workspace_id,
            "name": name,
            "created_at": time.time(),
            "last_active_at": time.time(),
        }
        safe_write_json(manifest_path, manifest_data)
        return ws_path

    def load_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """Loads and validates a workspace manifest.

        Args:
            workspace_id: Slug ID.

        Returns:
            Dict[str, Any]: The workspace manifest metadata.
        """
        ws_path = self.workspaces_root / workspace_id
        manifest_path = ws_path / "workspace.json"

        if not manifest_path.is_file():
            # If default doesn't exist, create it dynamically
            if workspace_id == "default":
                self.create_workspace("default", "Default Workspace")
            else:
                raise WorkspaceNotFoundError(workspace_id)

        data = safe_read_json(manifest_path)
        if not data:
            raise WorkspaceNotFoundError(workspace_id)

        # Touch last active timestamp
        data["last_active_at"] = time.time()
        safe_write_json(manifest_path, data)

        self.active_workspace_id = workspace_id
        return data

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """Lists metadata for all initialized workspaces.

        Returns:
            List[Dict[str, Any]]: List of workspace manifests.
        """
        workspaces = []
        if not self.workspaces_root.exists():
            return workspaces

        for child in self.workspaces_root.iterdir():
            if child.is_dir() and (child / "workspace.json").exists():
                data = safe_read_json(child / "workspace.json")
                if data:
                    workspaces.append(data)
        return workspaces

    def delete_workspace(self, workspace_id: str) -> bool:
        """Deletes a workspace directory tree.

        Prevents deleting the active workspace.

        Args:
            workspace_id: Slug ID.

        Returns:
            bool: True if deleted successfully.
        """
        if workspace_id == self.active_workspace_id:
            return False

        ws_path = self.workspaces_root / workspace_id
        if ws_path.is_dir():
            import shutil
            shutil.rmtree(ws_path)
            return True
        return False
