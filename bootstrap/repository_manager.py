"""Subprocess git wrapper managing repository clones, checkouts, and structure verification."""

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("bootstrap.repository")


class RepositoryManager:
    """Clones, updates, checks out, and validates the git codebase."""

    def __init__(self, target_dir: Path, repo_url: str):
        """Initializes the RepositoryManager.

        Args:
            target_dir: Destination path where the repo should reside.
            repo_url: Repository Git URL.
        """
        self.target_dir = target_dir
        self.repo_url = repo_url

    def is_cloned(self) -> bool:
        """Checks if the repository has been cloned already.

        Returns:
            bool: True if a .git directory exists inside target_dir.
        """
        return (self.target_dir / ".git").is_dir()

    def clone(self) -> bool:
        """Clones the repository.

        Returns:
            bool: True if cloning was successful.
        """
        logger.info(f"Cloning repository {self.repo_url} into {self.target_dir}...")
        try:
            self.target_dir.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", self.repo_url, str(self.target_dir)],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info("[+] Clone completed successfully.")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"[-] Clone failed: {e}")
            return False

    def update(self) -> bool:
        """Pulls the latest changes from remote.

        Returns:
            bool: True if update succeeded.
        """
        if not self.is_cloned():
            return False

        logger.info("Fetching updates from remote...")
        try:
            subprocess.run(
                ["git", "-C", str(self.target_dir), "fetch", "--all"],
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"[-] Fetch failed: {e}. Checking offline fallback...")
            return False

    def checkout(self, ref: str) -> bool:
        """Checks out a specific branch, tag, or commit hash.

        Args:
            ref: Git ref target.

        Returns:
            bool: True if checkout succeeded.
        """
        if not self.is_cloned():
            return False

        logger.info(f"Checking out ref: {ref}...")
        try:
            subprocess.run(
                ["git", "-C", str(self.target_dir), "checkout", ref],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"[+] Checkout to {ref} successful.")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"[-] Checkout failed: {e}")
            return False

    def validate_integrity(self) -> bool:
        """Validates that key folders (runtime, configs, tests) are present.

        Returns:
            bool: True if structure is correct.
        """
        required_paths = ["runtime", "configs", "tests", "requirements.txt"]
        for p in required_paths:
            if not (self.target_dir / p).exists():
                logger.warning(f"[-] Integrity validation failed: missing '{p}'")
                return False
        return True
