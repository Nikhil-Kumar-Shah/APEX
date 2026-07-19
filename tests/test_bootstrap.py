"""Unit tests for bootstrapping, repository manager, and deployment lifecycle."""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


from bootstrap.version_manager import VersionManager
from bootstrap.repository_manager import RepositoryManager
from bootstrap.dependency_manager import DependencyInstaller
from bootstrap.migration import MigrationManager
from bootstrap.validator import SystemValidator
from bootstrap.installer import InstallationWizard
from bootstrap.launcher import RuntimeLauncher


def test_bootstrap_version_manager():
    """Checks version resolution targets for branches/commits/stable tag modes."""
    vm = VersionManager("stable")
    assert vm.get_checkout_ref() == "v1.0.0"

    vm_latest = VersionManager("latest")
    assert vm_latest.get_checkout_ref() == "main"

    vm_custom = VersionManager("commit", custom_ref="abc123hash")
    assert vm_custom.get_checkout_ref() == "abc123hash"


def test_repository_manager_checks(tmp_path: Path):
    """Checks RepositoryManager path validations."""
    rm = RepositoryManager(tmp_path, "https://github.com/org/repo.git")
    assert not rm.is_cloned()
    assert not rm.validate_integrity()

    # Create dummy .git folder to mock cloning
    (tmp_path / ".git").mkdir()
    assert rm.is_cloned()


def test_dependency_installer():
    """Verifies that installed dependencies check returns True for standard libs."""
    installer = DependencyInstaller()
    assert installer.is_installed("sys")
    assert installer.is_installed("os")
    assert not installer.is_installed("missing_lib_xyz_99")


def test_migration_manager(tmp_path: Path):
    """Checks config backup creation, modification updates, and rollbacks."""
    config_file = tmp_path / "config.json"
    config_file.write_text('{"project_id": "test"}', encoding="utf-8")

    mgr = MigrationManager(config_file)
    assert mgr.backup()
    assert mgr.backup_path.is_file()

    # Modify
    config_file.write_text('{"project_id": "modified"}', encoding="utf-8")
    
    # Rollback
    assert mgr.rollback()
    assert "test" in config_file.read_text(encoding="utf-8")


def test_system_validator(tmp_path: Path):
    """Checks SystemValidator folder verification and auto-repair configuration."""
    validator = SystemValidator(tmp_path)
    
    # Directory checks
    assert validator.validate_directories(["cache", "logs"])
    assert (tmp_path / "cache").is_dir()
    assert (tmp_path / "logs").is_dir()

    # Config repair
    config_path = tmp_path / "configs" / "apex.config.json"

    assert validator.validate_and_repair_configuration(config_path)
    assert config_path.is_file()


@patch("bootstrap.dependency_manager.DependencyInstaller.install_requirements", return_value=True)
@patch("bootstrap.repository_manager.RepositoryManager.validate_integrity", return_value=True)
@patch("bootstrap.repository_manager.subprocess.run")
def test_installation_wizard(mock_run, mock_validate, mock_install, tmp_path: Path):
    """Tests wizard cloning, dependency checks, and path compilation."""
    # Mock Git clone command output to make it return success
    mock_run.return_value = MagicMock(returncode=0)

    wizard = InstallationWizard(tmp_path, "https://github.com/org/repo.git")
    
    # Run in silent/non-interactive mode
    target_path = wizard.run(
        interactive=False,
        version_mode="latest",
        use_persistent_drive=False,
    )

    assert target_path is not None
    assert target_path.name == "APEX"




def test_runtime_launcher(tmp_path: Path):
    """Tests system search paths updates and launcher execution errors."""
    launcher = RuntimeLauncher(tmp_path)
    launcher.configure_sys_path()
    
    # Verify path was added to sys.path
    assert str(tmp_path.resolve()) in sys.path

    # Force import error to verify launch returns False on failure
    with patch("builtins.__import__", side_effect=ImportError("Mocked Import Error")):
        assert not launcher.launch()

