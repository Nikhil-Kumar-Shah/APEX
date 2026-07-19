"""Centralized bootstrap configuration parameters."""

from pathlib import Path
from typing import List

# Repository Parameters
REPOSITORY_URL = "https://github.com/Nikhil-Kumar-Shah/APEX.git"
DEFAULT_BRANCH = "main"
MIN_PYTHON_VERSION = (3, 8)

# Default Installation Targets
DEFAULT_LOCAL_DIR_NAME = "APEX"
DEFAULT_COLAB_TEMP_DIR = Path("/content/APEX")
DEFAULT_COLAB_PERSISTENT_DIR = Path("/content/drive/MyDrive/APEX")

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
