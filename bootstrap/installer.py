"""Bootstrapping installation wizard."""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from bootstrap.config import DEFAULT_BRANCH, REPOSITORY_URL
from bootstrap.dependency_manager import DependencyInstaller
from bootstrap.repository_manager import RepositoryManager
from bootstrap.version_manager import VersionManager
from bootstrap.validator import SystemValidator


class InstallationWizard:
    """Guides first-time users through repo updates, storage locations, and dependency setups."""

    def __init__(self, workspace_parent_dir: Path, repo_url: str = REPOSITORY_URL):
        """Initializes the InstallationWizard.

        Args:
            workspace_parent_dir: Folder containing project checkouts.
            repo_url: Repository Git URL.
        """
        self.workspace_parent_dir = workspace_parent_dir
        self.repo_url = repo_url

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
        print("\n" + "=" * 50)
        print("            APEX Installation Wizard")
        print("=" * 50)

        # 1. Choose location
        target_dir = self.workspace_parent_dir / "APEX"
        if interactive and sys.stdin.isatty():
            choice = input("Install to persistent Google Drive? (y/n) [n]: ").strip().lower()
            if choice == "y":
                print("[!] Note: Source code and runtime now always install to local VM storage for performance.")

        print(f"[+] Target Installation Directory: {target_dir}")

        # 2. Check Repository
        repo_mgr = RepositoryManager(target_dir, self.repo_url)
        v_mgr = VersionManager(version_mode, version_ref)
        checkout_ref = v_mgr.get_checkout_ref(target_dir)

        if not repo_mgr.is_cloned():
            success = repo_mgr.clone()
            if not success:
                print("[-] Installation failed during Git clone. Check network status.")
                return None
        else:
            print("[+] Existing repository detected.")
            # Run fetch update
            repo_mgr.update()

        # Checkout target version ref
        success = repo_mgr.checkout(checkout_ref)
        if not success:
            print(f"[-] Requested release or tag '{checkout_ref}' not found. Continuing with the default branch.")
            repo_mgr.checkout(DEFAULT_BRANCH)

        # 3. Validate structure
        validator = SystemValidator(target_dir)
        if not validator.validate_manifest():
            print("[-] Repository structure is invalid or corrupted.")
            return None

        # 4. Install dependencies
        dep_installer = DependencyInstaller(target_dir / "requirements.txt")
        print("[+] Installing Python package dependencies...")
        if not dep_installer.install_requirements():
            print("[-] Failed to install requirements. Attempting fallback launch...")

        # 5. Initialize config directories
        config_path = target_dir / "configs" / "apex.config.json"
        validator.validate_and_repair_configuration(config_path)

        print("[+] Installation and verification complete.")
        print("=" * 50 + "\n")
        return target_dir
