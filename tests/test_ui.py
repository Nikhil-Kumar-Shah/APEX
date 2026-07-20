"""Unit tests for the presentation, dashboard, and UI registry layers."""

import pytest
from pathlib import Path

from runtime.config.manager import ConfigManager
from runtime.core.health import HealthMonitor
from runtime.model.manager import ModelManager
from runtime.ui.registry import UIRegistry


def test_ui_registry_dynamic_loading():
    """Validates that the UI registry handles missing modules without crashing."""
    registry = UIRegistry()
    
    # Register a fake module
    registry.register("fake_dashboard", "runtime.ui.does_not_exist")
    
    # Try to load it - should return None and not raise ModuleNotFoundError
    module = registry.load("fake_dashboard")
    assert module is None
    
    # Check consistency reporting
    report = registry.validate_consistency()
    assert "fake_dashboard" in report["missing"]
    assert len(report["loaded"]) == 0

    # Register a real module (dashboard)
    registry.register("dashboard", "runtime.ui.dashboard")
    module = registry.load("dashboard")
    assert module is not None
    assert hasattr(module, "RuntimeDashboard")
    
    report = registry.validate_consistency()
    assert "dashboard" in report["loaded"]
    assert "fake_dashboard" in report["missing"]


def test_runtime_dashboard_headless(tmp_path: Path):
    """Checks minimal dashboard instantiation and headless rendering controls."""
    config_file = tmp_path / "config.json"
    
    # Save default config first
    from runtime.config.schema import DEFAULT_CONFIG_TEMPLATE
    config_manager = ConfigManager(config_file)
    config_manager.save(DEFAULT_CONFIG_TEMPLATE)

    model_mgr = ModelManager(tmp_path)
    health_mon = HealthMonitor(tmp_path, model_mgr)

    # Dynamic load
    registry = UIRegistry()
    registry.register("dashboard", "runtime.ui.dashboard")
    dashboard_module = registry.load("dashboard")
    assert dashboard_module is not None
    
    dashboard = dashboard_module.RuntimeDashboard()

    # Test headless render execution (should return string/mock object without throwing error)
    res = dashboard.render()
    assert res is not None
