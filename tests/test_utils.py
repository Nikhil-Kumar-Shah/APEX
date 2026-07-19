"""Unit tests for utility functions."""

import json
from pathlib import Path
from runtime.utils.env import detect_environment, is_colab
from runtime.utils.file import ensure_directory, safe_read_json, safe_write_json


def test_environment_detection():
    """Validates that environment detection returns expected types."""
    env = detect_environment()
    assert env in ["colab", "jupyter", "terminal"]
    assert isinstance(is_colab(), bool)


def test_file_utilities(tmp_path: Path):
    """Tests directory generation and safe JSON reading and writing."""
    test_dir = tmp_path / "subdir"
    result_dir = ensure_directory(test_dir)
    assert result_dir.exists()
    assert result_dir.is_dir()

    test_file = result_dir / "test.json"
    data = {"key": "value", "number": 42}

    # Write data
    assert safe_write_json(test_file, data)
    assert test_file.exists()

    # Read data
    read_data = safe_read_json(test_file)
    assert read_data == data

    # Read non-existent file
    assert safe_read_json(result_dir / "nonexistent.json") is None

    # Read corrupted file
    corrupt_file = result_dir / "corrupt.json"
    with open(corrupt_file, "w", encoding="utf-8") as f:
        f.write("{invalid-json}")
    assert safe_read_json(corrupt_file) is None
