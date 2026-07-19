"""Unit tests for validation framework."""

import pytest
from pathlib import Path
from runtime.validation.validators import (
    ConfigValidator,
    DependencyValidator,
    EnvironmentValidator,
    ValidationError,
)


def test_config_validator_valid():
    """Tests that a valid configuration passes validation without exceptions."""
    valid_config = {
        "project_id": "test-project-123",
        "project_name": "Test Project",
        "runtime_version": "1.0.0",
        "config_version": "1.0.0",
    }
    # Should not raise any error
    ConfigValidator.validate(valid_config)


def test_config_validator_invalid_types():
    """Tests that incorrect data types trigger validation errors."""
    invalid_config = {
        "project_id": 12345,  # Should be string
        "project_name": "Test Project",
        "runtime_version": "1.0.0",
        "config_version": "1.0.0",
    }
    with pytest.raises(ValidationError) as excinfo:
        ConfigValidator.validate(invalid_config)
    assert "must be of type str" in str(excinfo.value)


def test_config_validator_invalid_slug():
    """Tests that invalid project IDs trigger validation errors."""
    invalid_config = {
        "project_id": "Invalid Project Name With Spaces!",
        "project_name": "Test Project",
        "runtime_version": "1.0.0",
        "config_version": "1.0.0",
    }
    with pytest.raises(ValidationError) as excinfo:
        ConfigValidator.validate(invalid_config)
    assert "Invalid project_id" in str(excinfo.value)


def test_dependency_validator():
    """Tests dependency validations for installed vs missing modules."""
    DependencyValidator.validate_dependency("sys")  # standard lib

    with pytest.raises(ValidationError):
        DependencyValidator.validate_dependency("some_impossible_package_name_12345")


def test_environment_validator(tmp_path: Path):
    """Tests path accessibility validation under environment checks."""
    writable_dir = tmp_path / "writable"
    writable_dir.mkdir()

    # Should pass
    EnvironmentValidator.validate([writable_dir])
