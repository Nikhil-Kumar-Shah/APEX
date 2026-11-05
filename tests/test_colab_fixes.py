"""Regression tests for Google Colab deployment issues.

Covers:
- Issue 1: GPU detection, CPU warning banners, RAM compatibility, device propagation, no silent fallback.
- Issue 2: Duplicate notebook UI prevention, container cleanup, render() return semantics.
- Issue 3: Google Drive mount idempotency, non-forced remount, graceful fallback to local storage.
- Issue 4: Routine log isolation, StreamHandler removal, LogBufferHandler capture.
- Issue 5: Startup progress consistency, stage failure reflection, duplicate start prevention.
"""

import logging
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from runtime.config.profile import check_hardware_compatibility, estimate_vram
from runtime.config.schema import ApexConfig
from runtime.core.errors import ApexErrorCode, GPUNotFoundError, RuntimeErrorBase
from runtime.core.lifecycle import RuntimeLifecycle
from runtime.drive.manager import DriveManager
from runtime.engine.transformers_adapter import TransformersInferenceEngine
from runtime.logging.logger import WidgetLogHandler, remove_stream_handlers, setup_logger
from runtime.model.manager import ModelManager
from runtime.ui.launcher import APEXLauncher, LogBufferHandler, detect_environment_hardware


# ==============================================================================
# Issue 1: GPU Detection, CPU Warnings, RAM Compatibility & Device Propagation
# ==============================================================================

def test_detect_hardware_cpu_mode_fields():
    """Ensures hardware detection accurately reports CPU mode without fabricating GPU data."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.backends.mps.is_available.return_value = False
    with patch.dict(sys.modules, {"torch": mock_torch}):
        hw = detect_environment_hardware()
        assert hw["cuda_available"] is False
        assert hw["device"] == "cpu"
        assert "CPU" in hw["gpu_name"]
        assert hw["vram_total_gb"] is None


def test_hardware_html_cpu_warning_colab(tmp_path: Path):
    """Ensures a prominent Colab T4 GPU warning is rendered when running in Colab without GPU."""
    launcher = APEXLauncher(workspace_path=tmp_path)
    launcher.hardware_info = {
        "is_colab": True,
        "runtime_name": "Google Colab",
        "device": "cpu",
        "gpu_name": "None (CPU Mode)",
        "vram_total_gb": None,
        "ram_total_gb": 12.67,
        "ram_available_gb": 11.8,
        "cuda_available": False,
    }
    html_out = launcher._render_hardware_html()
    assert "Colab CPU Runtime Active" in html_out
    assert "T4 GPU" in html_out
    assert "Google Colab" in html_out


def test_hardware_html_cpu_notice_local(tmp_path: Path):
    """Ensures a clean CPU mode notice is rendered when running locally without GPU."""
    launcher = APEXLauncher(workspace_path=tmp_path)
    launcher.hardware_info = {
        "is_colab": False,
        "runtime_name": "Local Environment",
        "device": "cpu",
        "gpu_name": "None (CPU Mode)",
        "vram_total_gb": None,
        "ram_total_gb": 16.0,
        "ram_available_gb": 8.0,
        "cuda_available": False,
    }
    html_out = launcher._render_hardware_html()
    assert "CPU Mode Active" in html_out
    assert "T4 GPU" not in html_out  # Only Colab should suggest Colab menu


def test_hardware_compatibility_cpu_oom_prevention():
    """Ensures models larger than available system RAM are flagged incompatible on CPU."""
    # 7B model requires ~14 GB VRAM -> ~16.8 GB RAM estimate.
    # On a standard 12.0 GB RAM Colab instance, this must return 'incompatible'.
    status, msg = check_hardware_compatibility(
        repo_id="Qwen/Qwen2.5-7B-Instruct",
        vram_total_gb=0.0,
        cuda_available=False,
        precision="float16",
        ram_available_gb=12.0,
    )
    assert status == "incompatible"
    assert "exceeds available system RAM" in msg
    assert "T4 GPU" in msg

    # Small 0.5B model requires ~1.0 GB RAM, fits comfortably in 12.0 GB.
    status_small, msg_small = check_hardware_compatibility(
        repo_id="Qwen/Qwen2.5-0.5B",
        vram_total_gb=0.0,
        cuda_available=False,
        precision="float16",
        ram_available_gb=12.0,
    )
    assert status_small == "cpu"
    assert "Estimated RAM usage" in msg_small


def test_validate_inputs_rejects_incompatible_model_on_cpu(tmp_path: Path):
    """Ensures launcher.validate_inputs rejects models that would crash a CPU environment."""
    launcher = APEXLauncher(workspace_path=tmp_path)
    launcher.hardware_info = {
        "is_colab": True,
        "runtime_name": "Google Colab",
        "device": "cpu",
        "gpu_name": "None (CPU Mode)",
        "vram_total_gb": 0.0,
        "ram_total_gb": 12.67,
        "ram_available_gb": 11.5,
        "cuda_available": False,
    }

    is_valid, norm_id, errors = launcher.validate_inputs(
        "Qwen/Qwen2.5-7B-Instruct",
        precision="float16",
        port_str="8000",
    )
    assert is_valid is False
    assert any("Hardware Incompatibility" in e for e in errors)


def test_transformers_engine_explicit_cuda_fails_fast_when_unavailable():
    """Ensures TransformersInferenceEngine does not silently switch to CPU if CUDA was explicitly requested."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_transformers = MagicMock()

    with patch.dict(sys.modules, {"torch": mock_torch, "transformers": mock_transformers}):
        engine = TransformersInferenceEngine({"model_id": "mock/model"})
        with pytest.raises(GPUNotFoundError) as exc_info:
            engine.load_model("mock/path", parameters={"device": "cuda"})

        assert "CUDA is not available" in str(exc_info.value)
        assert exc_info.value.code == ApexErrorCode.GPU_NOT_AVAILABLE


def test_transformers_engine_device_cpu_respected():
    """Ensures TransformersInferenceEngine respects explicit device='cpu'."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_transformers = MagicMock()

    with patch.dict(sys.modules, {"torch": mock_torch, "transformers": mock_transformers}):
        engine = TransformersInferenceEngine({"model_id": "mock/model"})
        engine.load_model("mock/path", parameters={"device": "cpu"})
        assert engine.device == "cpu"


def test_model_manager_forwards_device_parameter(tmp_path: Path):
    """Ensures ModelManager forwards device parameter into engine load_model."""
    mgr = ModelManager(tmp_path / "cache")
    mock_engine = MagicMock()
    mock_engine.is_loaded = True
    mock_engine.generate_stream.return_value = ["verified"]

    with patch("runtime.model.manager.get_engine", return_value=mock_engine), \
         patch.object(mgr, "download_model", return_value=tmp_path / "cache" / "model"):
        mgr.load_model("Qwen/Qwen2.5-0.5B", device="cuda:0")

        # Verify engine.load_model received parameters with device="cuda:0"
        _, kwargs = mock_engine.load_model.call_args
        assert kwargs["parameters"]["device"] == "cuda:0"


# ==============================================================================
# Issue 2: Duplicate Notebook UI Prevention & Container Tracking
# ==============================================================================

def test_launcher_render_returns_none_in_widget_env(tmp_path: Path):
    """Ensures render() and render_shutdown() return None when widgets are displayed.

    Returning None prevents Jupyter's expression display hook from rendering
    the returned ipywidgets.VBox container a second time.
    """
    launcher = APEXLauncher(workspace_path=tmp_path)

    mock_widgets = MagicMock()
    mock_display_fn = MagicMock()
    mock_ipython = MagicMock()
    mock_ipython_display = MagicMock()
    mock_ipython_display.display = mock_display_fn
    mock_ipython_display.HTML = MagicMock()

    with patch.dict(sys.modules, {
        "ipywidgets": mock_widgets,
        "IPython": mock_ipython,
        "IPython.display": mock_ipython_display,
    }):
        res1 = launcher.render()
        assert res1 is None, "render() must return None to prevent Jupyter expression display duplicate"
        assert mock_display_fn.call_count >= 1

        res2 = launcher.render_shutdown()
        assert res2 is None, "render_shutdown() must return None to prevent duplicate"


def test_launcher_close_cleans_containers(tmp_path: Path):
    """Ensures launcher.close() safely disposes of widget containers."""
    launcher = APEXLauncher(workspace_path=tmp_path)

    mock_container = MagicMock()
    launcher._active_container = mock_container
    APEXLauncher._active_container = mock_container

    launcher.close()
    mock_container.close.assert_called()
    assert launcher._active_container is None
    assert APEXLauncher._active_container is None


def test_launcher_rerun_closes_previous_active_container(tmp_path: Path):
    """Ensures executing render() again closes the previously active container."""
    launcher = APEXLauncher(workspace_path=tmp_path)

    old_container = MagicMock()
    APEXLauncher._active_container = old_container

    mock_widgets = MagicMock()
    mock_ipython = MagicMock()
    mock_ipython_display = MagicMock()

    with patch.dict(sys.modules, {
        "ipywidgets": mock_widgets,
        "IPython": mock_ipython,
        "IPython.display": mock_ipython_display,
    }):
        launcher.render()
        old_container.close.assert_called_once()


# ==============================================================================
# Issue 3: Google Drive Mounting Idempotency & Graceful Fallback
# ==============================================================================

def test_drive_manager_is_drive_mounted(tmp_path: Path):
    """Ensures is_drive_mounted detects existing /content/drive/MyDrive directory."""
    dm = DriveManager(fallback_local_root=tmp_path)
    dm.mount_point = tmp_path / "drive"

    assert dm.is_drive_mounted() is False

    # Create mount point and MyDrive
    (tmp_path / "drive" / "MyDrive").mkdir(parents=True)
    assert dm.is_drive_mounted() is True


def test_drive_manager_mount_reuses_existing_mount(tmp_path: Path):
    """Ensures mount() does not invoke google.colab.drive.mount when already mounted."""
    dm = DriveManager(fallback_local_root=tmp_path)
    dm.is_colab_env = True
    dm.mount_point = tmp_path / "drive"
    (tmp_path / "drive" / "MyDrive").mkdir(parents=True)

    mock_colab_drive = MagicMock()
    with patch.dict(sys.modules, {"google.colab": MagicMock(drive=mock_colab_drive)}):
        ok = dm.mount()
        assert ok is True
        mock_colab_drive.mount.assert_not_called()
        assert dm.persistence_root == tmp_path / "drive" / "MyDrive" / "APEX"


def test_lifecycle_startup_continues_when_drive_mount_fails(tmp_path: Path):
    """Ensures RuntimeLifecycle.startup() does not abort when Drive fails to mount."""
    lifecycle = RuntimeLifecycle(workspace_path=tmp_path)
    # Simulate Drive mount failure
    lifecycle.drive_manager.mount = MagicMock(return_value=False)

    ok = lifecycle.startup(interactive=False)
    assert ok is True, "Lifecycle startup must succeed with local storage fallback when Drive mount fails"
    assert lifecycle.drive_manager.persistence_root == lifecycle.drive_manager.project_root


# ==============================================================================
# Issue 4: Routine Log Isolation & Output Leakage Prevention
# ==============================================================================

def test_remove_stream_handlers_cleans_stdout_stream():
    """Ensures remove_stream_handlers removes standard console StreamHandlers."""
    test_logger = logging.getLogger("test_isolation_logger")
    test_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    widget_handler = WidgetLogHandler()
    buffer_handler = LogBufferHandler()

    test_logger.addHandler(console_handler)
    test_logger.addHandler(widget_handler)
    test_logger.addHandler(buffer_handler)

    assert len(test_logger.handlers) == 3

    remove_stream_handlers(test_logger)

    # console_handler should be removed; widget and buffer handlers preserved
    assert console_handler not in test_logger.handlers
    assert widget_handler in test_logger.handlers
    assert buffer_handler in test_logger.handlers


def test_launcher_scoped_log_capture(tmp_path: Path):
    """Ensures launcher attaches LogBufferHandler with propagate=False to stop cell stdout leaks."""
    launcher = APEXLauncher(workspace_path=tmp_path)

    runtime_logger = logging.getLogger("runtime")
    assert runtime_logger.propagate is False
    assert launcher.log_handler in runtime_logger.handlers

    # Logging a message should land in buffer
    runtime_logger.info("Internal routine test event 12345")
    logs = launcher.log_handler.get_logs()
    assert "Internal routine test event 12345" in logs


# ==============================================================================
# Issue 5: Startup Progress Consistency & Failure Reporting
# ==============================================================================

def test_launcher_duplicate_launch_blocked(tmp_path: Path):
    """Ensures calling launch() while a launch is active is safely rejected."""
    launcher = APEXLauncher(workspace_path=tmp_path)
    launcher.is_launching = True

    started = launcher.launch()
    assert started is False


def test_launcher_stage_fails_gracefully_on_error(tmp_path: Path):
    """Ensures if an error occurs during launch, the stage is marked failed and UI does not hang."""
    launcher = APEXLauncher(workspace_path=tmp_path)

    completion_results = []

    with patch.object(RuntimeLifecycle, "startup", return_value=False):
        launcher.launch(on_complete=lambda ok, err: completion_results.append((ok, err)))

        # Wait for background thread
        for _ in range(50):
            if len(completion_results) > 0:
                break
            time.sleep(0.05)

    assert len(completion_results) == 1
    success, err_msg = completion_results[0]
    assert success is False
    assert "Runtime environment initialization failed" in str(err_msg)

    # Stage 1 should be marked 'failed', not stuck 'in_progress'
    st, detail = launcher.stage_states[1]
    assert st == "failed"
    assert launcher.is_launching is False
