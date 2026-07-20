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
            "python-multipart": "multipart",
            "ipywidgets": "ipywidgets",
        }
        
        # Strip version specifiers like ==1.0.0 or >=2.0
        clean_name = package_name.split("=")[0].split(">")[0].split("<")[0].split("~")[0].strip()
        
        import_name = import_map.get(clean_name.lower(), clean_name.replace("-", "_"))
        try:
            spec = importlib.util.find_spec(import_name)
            return spec is not None
        except Exception:
            return False

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

        logger.info(f"Installing missing dependencies: {', '.join(package_list)}", extra={"prefix": "SYSTEM"})
        
        for attempt in range(retries):
            try:
                cmd = [sys.executable, "-m", "pip", "install", "-q"] + package_list
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                logger.info("Package installations finished successfully.", extra={"prefix": "SUCCESS"})
                return True
            except subprocess.CalledProcessError as e:
                logger.warning(f"Installation attempt {attempt+1} failed: {e.stderr}", extra={"prefix": "WARNING"})
                if attempt == retries - 1:
                    logger.error("All dependency installation retries failed.", extra={"prefix": "ERROR"})
                    return False
        return False

    def install_requirements(self) -> bool:
        """Parses requirements.txt, skips existing, installs missing."""
        if not self.requirements_path or not self.requirements_path.is_file():
            logger.warning("requirements.txt path is missing or invalid.", extra={"prefix": "WARNING"})
            return False

        logger.info(f"Analyzing dependencies from: {self.requirements_path}", extra={"prefix": "SYSTEM"})
        
        try:
            content = self.requirements_path.read_text(encoding="utf-8")
            packages = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
            
            missing = []
            installed = []
            
            for pkg in packages:
                if self.is_installed(pkg):
                    installed.append(pkg)
                else:
                    missing.append(pkg)
            
            if installed:
                logger.info(f"Skipped {len(installed)} already installed packages.", extra={"prefix": "SYSTEM"})
            
            if not missing:
                logger.info("All dependencies are already satisfied.", extra={"prefix": "SUCCESS"})
                return True
                
            logger.info(f"Found {len(missing)} missing packages to install.", extra={"prefix": "SYSTEM"})
            return self.install(missing)
            
        except Exception as e:
            logger.error(f"Requirements parsing/installation failed: {e}", extra={"prefix": "ERROR"})
            return False
