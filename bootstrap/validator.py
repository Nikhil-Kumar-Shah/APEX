"""System integrity validation and automatic repairs."""

import logging
from pathlib import Path
from typing import List

from runtime.config.schema import DEFAULT_CONFIG_TEMPLATE
from runtime.utils.file import safe_write_json
from bootstrap.dependency_manager import DependencyInstaller

logger = logging.getLogger("bootstrap.validator")


class SystemValidator:
    """Verifies directory setups, installed packages, and repairs corrupted/missing assets."""

    def __init__(self, project_root: Path):
        """Initializes the SystemValidator.

        Args:
            project_root: Repository root path.
        """
        self.project_root = project_root
        self.dep_installer = DependencyInstaller()

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
