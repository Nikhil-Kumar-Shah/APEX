"""System integrity validation and manifest-based structures checks."""

import logging
from pathlib import Path
from typing import List

from runtime.config.schema import DEFAULT_CONFIG_TEMPLATE
from runtime.utils.file import safe_write_json
from bootstrap.config import REQUIRED_MANIFEST
from bootstrap.dependency_manager import DependencyInstaller

logger = logging.getLogger("bootstrap.validator")


class SystemValidator:
    """Verifies directory setups, installed packages, and checks codebase manifests."""

    def __init__(self, project_root: Path):
        """Initializes the SystemValidator.

        Args:
            project_root: Repository root path.
        """
        self.project_root = project_root
        self.dep_installer = DependencyInstaller()

    def validate_manifest(self) -> bool:
        """Validates existence of required manifest paths in the repository.

        Returns:
            bool: True if validation succeeds.
        """
        missing_paths = []
        for path_str in REQUIRED_MANIFEST:
            target_path = self.project_root / path_str
            if not target_path.exists():
                missing_paths.append(path_str)

        if missing_paths:
            logger.error("[-] Repository validation failed! Structural files/folders are missing:")
            for mp in missing_paths:
                logger.error(f"  - Missing: {mp}")
            logger.error("[!] Suggestion: Run a clean re-clone or pull the default branch to repair files.")
            return False

        logger.info("[+] Repository validation completed successfully.")
        return True

    def validate_directories(self, required_dirs: List[str]) -> bool:
        """Verifies directories exist, auto-creating them if missing.

        Args:
            required_dirs: Directories that must be present.

        Returns:
            bool: True if directories are present or repaired.
        """
        for d in required_dirs:
            path = self.project_root / d
            if not path.is_dir():
                logger.info(f"[!] Directory missing: '{d}'. Creating folder...")
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    logger.error(f"[-] Failed to repair directory '{d}': {e}")
                    return False
        return True

    def validate_dependencies(self, required_packages: List[str]) -> bool:
        """Checks and reports if dependencies are missing.

        Args:
            required_packages: List of packages.

        Returns:
            bool: True if all packages are installed.
        """
        missing = []
        for pkg in required_packages:
            if not self.dep_installer.is_installed(pkg):
                missing.append(pkg)
        
        if missing:
            logger.warning(f"[-] Missing python packages: {missing}")
            return False
        return True

    def validate_and_repair_configuration(self, config_path: Path) -> bool:
        """Validates configuration files, writing default templates if missing.

        Args:
            config_path: Path to the JSON configuration file.

        Returns:
            bool: True if configuration is verified.
        """
        if not config_path.is_file():
            logger.info(f"[!] Configuration file missing: {config_path}. Writing default template...")
            try:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                success = safe_write_json(config_path, DEFAULT_CONFIG_TEMPLATE)
                return success
            except Exception as e:
                logger.error(f"[-] Configuration repair failed: {e}")
                return False
        return True
