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
        """Verifies if a python package is currently installed and satisfies constraints.

        Args:
            package_name: Package requirement string (e.g. 'fastapi>=0.100.0').

        Returns:
            bool: True if installed and constraint satisfied.
        """
        # 1. Attempt precise version requirement checking if packaging is available
        try:
            import importlib.metadata
            from packaging.requirements import Requirement
            req = Requirement(package_name)
            try:
                installed_ver = importlib.metadata.version(req.name)
                if req.specifier and not req.specifier.contains(installed_ver, prereleases=True):
                    return False
                return True
            except importlib.metadata.PackageNotFoundError:
                pass
        except Exception:
            pass

        # 2. Fallback to module spec resolution
        import_map = {
            "pyngrok": "pyngrok",
            "fastapi": "fastapi",
            "uvicorn": "uvicorn",
            "huggingface-hub": "huggingface_hub",
            "huggingface_hub": "huggingface_hub",
            "colorama": "colorama",
            "pydantic": "pydantic",
            "python-multipart": "multipart",
            "ipywidgets": "ipywidgets",
            "torch": "torch",
            "transformers": "transformers",
            "requests": "requests",
            "httpx": "httpx",
            "pytest": "pytest",
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
        """Executes pip install commands with output capture.

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
                cmd = [sys.executable, "-m", "pip", "install", "--no-warn-script-location"] + package_list
                p = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                if p.stdout:
                    for line in p.stdout:
                        line_str = line.strip()
                        if line_str:
                            logger.info(f"pip: {line_str}")
                p.wait()

                if p.returncode == 0:
                    logger.info("Package installations finished successfully.", extra={"prefix": "SUCCESS"})
                    return True
                else:
                    logger.warning(f"Installation attempt {attempt+1} failed with return code {p.returncode}", extra={"prefix": "WARNING"})
            except Exception as e:
                logger.warning(f"Installation attempt {attempt+1} failed: {e}", extra={"prefix": "WARNING"})

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
                logger.info(f"Skipped {len(installed)} already satisfied dependencies.", extra={"prefix": "SYSTEM"})
            
            if not missing:
                logger.info("All dependencies are already satisfied.", extra={"prefix": "SUCCESS"})
                return True
                
            logger.info(f"Found {len(missing)} missing packages to install.", extra={"prefix": "SYSTEM"})
            return self.install(missing)
            
        except Exception as e:
            logger.error(f"Requirements parsing/installation failed: {e}", extra={"prefix": "ERROR"})
            return False
