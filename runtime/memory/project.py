"""Project preferences and state persistence."""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.utils.file import safe_read_json, safe_write_json


class ProjectMemory:
    """Manages project-specific preferences, active configurations, and model selection histories."""

    def __init__(self, workspace_path: Path):
        """Initializes the ProjectMemory.

        Args:
            workspace_path: Path of the active workspace.
        """
        self.workspace_path = workspace_path
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    @property
    def projects_dir(self) -> Path:
        """Gets the directory of projects storage."""
        return self.workspace_path / "projects"

    def _get_project_path(self, project_id: str) -> Path:
        return self.projects_dir / f"{project_id}.project.json"

    def save_project(self, project_id: str, name: str, state: Dict[str, Any], preferences: Optional[Dict[str, Any]] = None) -> None:
        """Saves project metadata and current workspace layout states.

        Args:
            project_id: Unique project slug.
            name: Readable name of the project.
            state: Dictionary containing loaded model, active files, cursor position.
            preferences: User configuration preferences.
        """
        filepath = self._get_project_path(project_id)
        
        # Load existing project to preserve history if needed
        existing = safe_read_json(filepath) or {}

        project_data = {
            "project_id": project_id,
            "name": name,
            "updated_at": time.time(),
            "created_at": existing.get("created_at", time.time()),
            "state": state,
            "preferences": preferences or existing.get("preferences", {}),
            "history": existing.get("history", []),
        }

        # Track history logs: append active model switch events
        active_model = state.get("active_model_id")
        if active_model and (not project_data["history"] or project_data["history"][-1].get("model") != active_model):
            project_data["history"].append(
                {
                    "timestamp": time.time(),
                    "model": active_model,
                    "engine": state.get("active_engine"),
                }
            )

        # Cap history list to latest 10 models
        project_data["history"] = project_data["history"][-10:]

        safe_write_json(filepath, project_data)

    def load_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Loads project configuration data.

        Args:
            project_id: Unique project slug.

        Returns:
            Optional[Dict[str, Any]]: Project metadata or None if missing.
        """
        filepath = self._get_project_path(project_id)
        return safe_read_json(filepath)

    def list_projects(self) -> List[Dict[str, Any]]:
        """Lists all registered project records.

        Returns:
            List[Dict[str, Any]]: List of project metadata.
        """
        projects = []
        if not self.projects_dir.exists():
            return projects

        for child in self.projects_dir.glob("*.project.json"):
            data = safe_read_json(child)
            if data:
                projects.append(
                    {
                        "project_id": data["project_id"],
                        "name": data["name"],
                        "updated_at": data["updated_at"],
                        "last_model": data["state"].get("active_model_id"),
                    }
                )
        return projects
