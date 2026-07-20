"""Centralized bootstrap configuration parameters."""

from dataclasses import dataclass
from pathlib import Path
from typing import List

@dataclass
class BootstrapConfig:
    """Core configuration for the APEX bootstrap sequence."""
    repo_url: str = "https://github.com/Nikhil-Kumar-Shah/APEX.git"
    default_branch: str = "main"
    min_python_version: tuple = (3, 8)
    
    # Target directory on Colab
    colab_target_dir: Path = Path("/content/APEX")
    colab_persistent_dir: Path = Path("/content/drive/MyDrive/APEX")


# Centralized Validation Manifest
# Only checks source-controlled assets; ignores directories created post-launch.
REQUIRED_MANIFEST: List[str] = [
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "bootstrap/__init__.py",
    "runtime/__init__.py",
    "notebook/APEX.ipynb",
    "docs/DEVELOPER_GUIDE.md",
    "tests/test_bootstrap.py",
]
