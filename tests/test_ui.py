"""Unit tests for the presentation, dashboard, and UI layers."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from runtime.config.manager import ConfigManager
from runtime.core.health import HealthMonitor
from runtime.model.manager import ModelManager
from runtime.ui.benchmarks import BenchmarkTracker
from runtime.ui.dashboard import RuntimeDashboard
from runtime.ui.logs import LogViewer
from runtime.ui.updater import UpdateChecker


def test_update_checker():
    """Checks that the update checker detects out of date version levels."""
    # Same version
    checker = UpdateChecker(current_runtime_version="1.0.0", current_config_version="1.0.0")
    res = checker.check_for_updates()
    assert not res["update_available"]

    # Older version
    checker_old = UpdateChecker(current_runtime_version="0.9.0", current_config_version="0.9.0")
    res_old = checker_old.check_for_updates()
    assert res_old["update_available"]
    assert res_old["runtime_update_available"]
    assert res_old["config_update_available"]


def test_benchmark_tracker():
    """Validates that BenchmarkTracker logs runs and calculates correct averages."""
    tracker = BenchmarkTracker()
    assert tracker.get_summary()["total_runs"] == 0

    tracker.record_run(
        model_id="qwen-1.5b",
        engine="mock",
        load_time=1.0,
        ttft=0.05,
        tokens_count=50,
        generation_time=2.0,
    )
    tracker.record_run(
        model_id="qwen-1.5b",
        engine="mock",
        load_time=2.0,
        ttft=0.15,
        tokens_count=100,
        generation_time=4.0,
    )

    summary = tracker.get_summary()
    assert summary["total_runs"] == 2
    assert summary["average_tokens_per_second"] == 25.0
    assert summary["average_ttft_sec"] == 0.10
    assert summary["average_load_time_sec"] == 1.5


def test_log_viewer(tmp_path: Path):
    """Tests log searching and severity level filters."""
    log_file = tmp_path / "runtime.log"
    log_file.write_text(
        "[2026-07-20 00:00:00] [INFO] (runtime) Starting server...\n"
        "[2026-07-20 00:00:01] [WARNING] (runtime) Low memory warnings\n"
        "[2026-07-20 00:00:02] [ERROR] (runtime) GPU Out of memory exception\n",
        encoding="utf-8"
    )

    viewer = LogViewer(log_file)

    # Fetch all
    lines = viewer.fetch_logs(limit=10)
    assert len(lines) == 3

    # Severity filter
    warnings = viewer.fetch_logs(limit=10, level_filter="WARNING")
    assert len(warnings) == 1
    assert "Low memory warnings" in warnings[0]

    # Search filter
    gpu_logs = viewer.fetch_logs(limit=10, search_query="GPU")
    assert len(gpu_logs) == 1
    assert "GPU Out of memory" in gpu_logs[0]


def test_runtime_dashboard(tmp_path: Path):
    """Checks dashboard settings saving and headless rendering controls."""
    config_file = tmp_path / "config.json"
    
    # Save default config first
    from runtime.config.schema import DEFAULT_CONFIG_TEMPLATE
    config_manager = ConfigManager(config_file)
    config_manager.save(DEFAULT_CONFIG_TEMPLATE)

    model_mgr = ModelManager(tmp_path)
    health_mon = HealthMonitor(tmp_path, model_mgr)

    dashboard = RuntimeDashboard(config_manager, model_mgr, health_mon, tmp_path / "runtime.log")

    # Verify settings saving via UI interface binds
    new_form_data = {
        "project_id": "dashboard-modified-id",
        "project_name": "Dashboard Modified Name",
    }
    assert dashboard.save_settings_ui(new_form_data)
    
    # Verify loaded settings reflect change
    loaded = config_manager.load()
    assert loaded["project_id"] == "dashboard-modified-id"
    assert loaded["project_name"] == "Dashboard Modified Name"

    # Test headless render execution (should return string/mock object without throwing error)
    res = dashboard.render()
    assert res is not None
