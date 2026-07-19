"""Project Identity Module."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class ProjectIdentity:
    """Represents the core identity of the runtime project."""

    project_id: str
    project_name: str
    runtime_version: str
    config_version: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "ProjectIdentity":
        """Builds a ProjectIdentity instance from a configuration dictionary.

        Args:
            config: Configuration dictionary.

        Returns:
            ProjectIdentity: The mapped identity object.
        """
        # Creation time can be loaded from metadata if exists, otherwise defaults to now
        created = config.get("created_at") or datetime.utcnow().isoformat()
        modified = config.get("last_modified") or datetime.utcnow().isoformat()

        return cls(
            project_id=config["project_id"],
            project_name=config["project_name"],
            runtime_version=config["runtime_version"],
            config_version=config["config_version"],
            created_at=created,
            last_modified=modified,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts identity to a dictionary representation.

        Returns:
            Dict[str, Any]: Serialized identity dictionary.
        """
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "runtime_version": self.runtime_version,
            "config_version": self.config_version,
            "created_at": self.created_at,
            "last_modified": self.last_modified,
        }
