"""Bootstrapping installation wizard."""

import sys
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from bootstrap.config import BootstrapConfig
from bootstrap.dependency_manager import DependencyInstaller
from bootstrap.repository_manager import RepositoryManager
from bootstrap.version_manager import VersionManager
from bootstrap.validator import SystemValidator

logger = logging.getLogger("bootstrap.installer")


class InstallationWizard:
    """Guides first-time users through repo updates, storage locations, and dependency setups."""

    def __init__(self, workspace_parent_dir: Path, repo_url: Optional[str] = None):
        """Initializes the wizard.

        Args:
            workspace_parent_dir: The directory where the repo will be cloned.
            repo_url: Optional GitHub URL.
        """
        self.workspace_parent_dir = workspace_parent_dir.resolve()
        self.repo_url = repo_url or BootstrapConfig().repo_url

    def run(
        self,
        interactive: bool = True,
        version_mode: str = "stable",
        version_ref: Optional[str] = None,
        use_persistent_drive: bool = False,
    ) -> Optional[Path]:
        """Runs the installation wizard.

        Args:
            interactive: Whether to prompt for values.
            version_mode: Mode string (stable, latest, branch, commit).
            version_ref: Custom tag or branch.
            use_persistent_drive: Force Google Drive location.

        Returns:
            Optional[Path]: Target project repository directory path.
        """
        logger.info("=" * 50, extra={"prefix": "SYSTEM"})
        logger.info("APEX Installation Wizard", extra={"prefix": "SYSTEM"})
        logger.info("=" * 50, extra={"prefix": "SYSTEM"})

        # 1. Choose location
        target_dir = self.workspace_parent_dir / "APEX"
        if interactive and sys.stdin.isatty():
            choice = input("Install to persistent Google Drive? (y/n) [n]: ").strip().lower()
            if choice == "y":
                logger.info("Note: Source code and runtime now always install to local VM storage for performance.", extra={"prefix": "WARNING"})

        logger.info(f"Target Installation Directory: {target_dir}", extra={"prefix": "SYSTEM"})

        # 2. Check Repository
        repo_mgr = RepositoryManager(target_dir, self.repo_url)
        v_mgr = VersionManager(version_mode, version_ref)
        checkout_ref = v_mgr.get_checkout_ref(target_dir)

        if not repo_mgr.is_cloned():
            success = repo_mgr.clone()
            if not success:
                logger.error("Installation failed during Git clone. Check network status.", extra={"prefix": "ERROR"})
                return None
        else:
            logger.info("Existing repository detected.", extra={"prefix": "SUCCESS"})
            # Run fetch update
            repo_mgr.update()

        # Checkout target version ref
        success = repo_mgr.checkout(checkout_ref)
        if not success:
            logger.warning(f"Requested release or tag '{checkout_ref}' not found. Continuing with the default branch.", extra={"prefix": "WARNING"})
            repo_mgr.checkout(BootstrapConfig().default_branch)

        # 3. Validate structure
        validator = SystemValidator(target_dir)
        if not validator.validate_manifest():
            logger.error("Repository structure is invalid or corrupted.", extra={"prefix": "ERROR"})
            return None

        # 4. Install dependencies
        dep_installer = DependencyInstaller(target_dir / "requirements.txt")
        logger.info("Installing Python package dependencies...", extra={"prefix": "SYSTEM"})
        if not dep_installer.install_requirements():
            logger.warning("Failed to install requirements. Attempting fallback launch...", extra={"prefix": "WARNING"})

        # 5. Initialize config directories
        config_path = target_dir / "workspaces" / "default" / "config.json"
        validator.validate_and_repair_configuration(config_path)

        logger.info("Installation and verification complete.", extra={"prefix": "SUCCESS"})
        logger.info("=" * 50, extra={"prefix": "SYSTEM"})
        return target_dir
