"""Version resolution management for repository checkouts."""

from typing import Any, Dict, Optional


class VersionManager:
    """Manages version settings, targets, and checks for release tags/commits."""

    def __init__(self, selected_version: str = "stable", custom_ref: Optional[str] = None):
        """Initializes the VersionManager.

        Args:
            selected_version: Version mode ('stable', 'latest', 'branch', 'commit').
            custom_ref: Specific branch name, tag, or commit hash.
        """
        self.selected_version = selected_version.lower().strip()
        self.custom_ref = custom_ref

    def get_checkout_ref(self) -> str:
        """Determines the Git reference string to check out.

        Returns:
            str: Git branch name, tag name, or commit hash.
        """
        if self.selected_version == "stable":
            # Defaults to main release tag or main branch
            return "v1.0.0"
        elif self.selected_version == "latest":
            return "main"
        elif self.selected_version in ["branch", "commit"] and self.custom_ref:
            return self.custom_ref
        return "main"

    def get_status(self) -> Dict[str, Any]:
        """Gets diagnostic status info.

        Returns:
            Dict[str, Any]: Version mode parameters.
        """
        return {
            "version_mode": self.selected_version,
            "target_ref": self.get_checkout_ref(),
            "custom_ref": self.custom_ref,
        }
