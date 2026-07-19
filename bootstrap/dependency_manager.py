"""Python package dependency checker and installer."""

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("bootstrap.dependency")


class DependencyInstaller:
    """Detects missing modules, triggers pip installs, and validates packages versions."""

    def __init__(self, requirements_path: Optional[Path] = None):
        """Initializes the DependencyInstaller.

        Args:
            requirements_path: Optional path to requirements.txt.
        """
        self.requirements_path = requirements_path

    @staticmethod
    def is_installed(package_name: str) -> bool:
        """Verifies if a python package is currently installed.

        Args:
            package_name: Module import name.

        Returns:
            bool: True if importable.
        """
        # Map package distribution name to python import name where necessary
        import_map = {
            "pyngrok": "pyngrok",
            "fastapi": "fastapi",
            "uvicorn": "uvicorn",
            "huggingface-hub": "huggingface_hub",
            "colorama": "colorama",
            "pydantic": "pydantic",
        }
        import_name = import_map.get(package_name.lower(), package_name)
        spec = importlib.util.find_spec(import_name)
        return spec is not None

    def install(self, package_list: List[str], retries: int = 2) -> bool:
        """Executes pip install commands.

        Args:
            package_list: List of packages to install.
            retries: Number of installation attempts.

        Returns:
            bool: True if installation succeeded.
        """
        if not package_list:
            return True

        logger.info(f"Installing missing dependencies: {package_list}...")
        
        for attempt in range(retries):
            try:
                cmd = [sys.executable, "-m", "pip", "install"] + package_list
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                logger.info("[+] Package installations finished successfully.")
                return True
            except subprocess.CalledProcessError as e:
                logger.warning(f"[-] Installation attempt {attempt+1} failed: {e.stderr}")
                if attempt == retries - 1:
                    logger.error("[-] All dependency installation retries failed.")
                    return False
        return False

    def install_requirements(self) -> bool:
        """Parses and installs packages listed inside requirements.txt."""
        if not self.requirements_path or not self.requirements_path.is_file():
            logger.warning("[-] requirements.txt path is missing or invalid.")
            return False

        logger.info(f"Installing dependencies from: {self.requirements_path}")
        try:
            cmd = [sys.executable, "-m", "pip", "install", "-r", str(self.requirements_path)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"[-] Requirements installation failed: {e.stderr}")
            return False
