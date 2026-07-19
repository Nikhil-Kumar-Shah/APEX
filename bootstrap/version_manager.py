"""Version resolution management for repository checkouts."""

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from bootstrap.config import DEFAULT_BRANCH

logger = logging.getLogger("bootstrap.version")


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

    def get_checkout_ref(self, repo_path: Optional[Path] = None) -> str:
        """Determines the Git reference string to check out.

        If stable mode is selected but no tags exist in the repo, automatically
        falls back to the default branch (Development Mode).

        Args:
            repo_path: Optional path to the repository directory.

        Returns:
            str: Git branch name, tag name, or commit hash.
        """
        has_tags = False
        if repo_path and repo_path.is_dir():
            try:
                res = subprocess.run(
                    ["git", "-C", str(repo_path), "tag"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                tags = [t.strip() for t in res.stdout.split("\n") if t.strip()]
                has_tags = len(tags) > 0
            except Exception as e:
                logger.debug(f"Could not read repository tags: {e}")
                has_tags = False

        if self.selected_version == "stable":
            if has_tags:
                return "v1.0.0"
            else:
                logger.info("No release tags found in repository. Auto-enabling Development Mode.")
                return DEFAULT_BRANCH
        elif self.selected_version == "latest":
            return DEFAULT_BRANCH
        elif self.selected_version in ["branch", "commit"] and self.custom_ref:
            return self.custom_ref
        return DEFAULT_BRANCH

    def get_status(self, repo_path: Optional[Path] = None) -> Dict[str, Any]:
        """Gets diagnostic status info.

        Returns:
            Dict[str, Any]: Version mode parameters.
        """
        return {
            "version_mode": self.selected_version,
            "target_ref": self.get_checkout_ref(repo_path),
            "custom_ref": self.custom_ref,
        }
