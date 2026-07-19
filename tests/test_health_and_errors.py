"""Unit tests for error classification and health monitoring."""

from pathlib import Path
from runtime.core.errors import GPUOutOfMemoryError, ModelNotFoundError
from runtime.core.health import HealthMonitor
from runtime.core.performance import PerformanceModeManager


def test_error_formatting():
    """Validates that custom exceptions produce structured formatting."""
    err = ModelNotFoundError("qwen-7b", log_info={"details": "custom log"})
    msg = str(err)

    assert "Model not found" in msg
    assert "qwen-7b" in msg
    assert "Double-check the model ID spelling" in msg  # recovery suggestion
    assert "custom log" in msg


def test_gpu_out_of_memory_error():
    """Validates VRAM allocation error suggestion text."""
    err = GPUOutOfMemoryError(requested_bytes=5000000000)
    msg = str(err)
    assert "Out of GPU Memory" in msg
    assert "5000000000" in msg
    assert "Enable quantization" in msg


def test_health_monitor(tmp_path: Path):
    """Validates that the HealthMonitor builds structured report dictionaries."""
    monitor = HealthMonitor(tmp_path)
    report = monitor.generate_report()

    assert "uptime_seconds" in report
    assert "disk" in report
    assert "ram" in report
    assert "gpu" in report
    assert "model_manager" in report

    assert "total_gb" in report["disk"]
    assert "available" in report["gpu"]


def test_performance_mode_manager():
    """Validates performance modes translate to correct configuration maps."""
    settings = PerformanceModeManager.get_settings("fast")
    assert settings["gpu_memory_utilization"] == 0.70
    assert settings["context_limit"] == 2048

    # Check custom override capability
    settings_override = PerformanceModeManager.get_settings("balanced", overrides={"context_limit": 999})
    assert settings_override["context_limit"] == 999
    assert settings_override["gpu_memory_utilization"] == 0.85
