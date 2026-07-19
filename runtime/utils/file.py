"""File and JSON operations utilities."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def ensure_directory(path: Path) -> Path:
    """Ensures a directory exists, creating it if necessary.

    Args:
        path: Path to the directory.

    Returns:
        Path: The validated/created directory path.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_read_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """Safely reads and parses a JSON file.

    Args:
        file_path: Path to the JSON file.

    Returns:
        Optional[Dict[str, Any]]: Parsed data or None if file doesn't exist or is invalid.
    """
    if not file_path.is_file():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def safe_write_json(file_path: Path, data: Dict[str, Any], indent: int = 4) -> bool:
    """Safely writes a dictionary to a JSON file.

    Uses a temporary file rename strategy to prevent file corruption.

    Args:
        file_path: Target JSON file path.
        data: Dictionary data to write.
        indent: Indentation spacing.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        ensure_directory(file_path.parent)
        temp_file = file_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        # Atomic replace
        if os.path.exists(file_path):
            os.remove(file_path)
        os.rename(temp_file, file_path)
        return True
    except OSError:
        # Cleanup temp file if it exists
        if "temp_file" in locals() and temp_file.exists():
            try:
                os.remove(temp_file)
            except OSError:
                pass
        return False
