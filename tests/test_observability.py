"""Comprehensive test suite for APEX Runtime Observability.

Covers:
- Authoritative stage state models & lifecycle transitions
- Real-time sub-operation progress emission without artificial percentages
- Startup stall detection watchdog (>= 45s non-abortive warning)
- Live Developer Console log capture, bounded buffer, level & query filtering
- Sensitive secret & token redaction (hf_..., Bearer ..., API keys, tunnel tokens)
- Development Mode vs. Release Mode presentation toggle
- Pipeline failure recovery and subsequent stage cancellation
"""

import logging
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from runtime.core.errors import ApexErrorCode, RuntimeErrorBase
from runtime.core.lifecycle import RuntimeLifecycle
from runtime.logging.logger import (
    LogBufferHandler,
    LogEntry,
    redact_sensitive_data,
)
from runtime.ui.launcher import (
    LAUNCH_STAGES,
    APEXLauncher,
    StageState,
    StageStatus,
)


# ── 1. StageStatus & StageState Models ───────────────────────────────────────

def test_stage_status_enum_values():
    """Verifies that all required lifecycle statuses are present in StageStatus."""
    expected = {"pending", "running", "completed", "failed", "warning", "cancelled"}
    actual = {s.value for s in StageStatus}
    assert actual == expected


def test_stage_state_initialization_and_elapsed_time():
    """Verifies StageState defaults, elapsed time calculation, and no fake percentages."""
    stage = StageState(stage_id=1, name="Environment Initialization")

    assert stage.stage_id == 1
    assert stage.name == "Environment Initialization"
    assert stage.status == StageStatus.PENDING
    assert stage.sub_operation == ""
    assert stage.progress_pct is None  # None for indeterminate; strictly no fake progress
    assert stage.is_stalled is False
    assert stage.elapsed_seconds == 0.0

    # Start stage
    stage.start_time = time.time() - 2.5
    stage.status = StageStatus.RUNNING
    assert stage.elapsed_seconds >= 2.4

    # Complete stage
    stage.end_time = stage.start_time + 3.0
    stage.status = StageStatus.COMPLETED
    assert round(stage.elapsed_seconds, 1) == 3.0


# ── 2. Authoritative Progress Tracking & Sub-Operations ──────────────────────

def test_launcher_set_stage_status_authoritative(tmp_path: Path):
    """Verifies authoritative status transitions and backward-compatible stage_states sync."""
    launcher = APEXLauncher(workspace_path=tmp_path)

    # Initially all stages are PENDING
    assert launcher.stages[1].status == StageStatus.PENDING
    assert launcher.stage_states[1] == ("pending", "")

    # Set Stage 1 to RUNNING with sub-operation
    launcher.set_stage_status(
        stage_id=1,
        status=StageStatus.RUNNING,
        detail="Initializing...",
        sub_op="[2/7] Checking persistent storage & Google Drive...",
    )

    assert launcher.stages[1].status == StageStatus.RUNNING
    assert launcher.stages[1].sub_operation == "[2/7] Checking persistent storage & Google Drive..."
    assert launcher.active_stage_id == 1
    # Backward compatible dict maps RUNNING to 'in_progress'
    assert launcher.stage_states[1][0] == "in_progress"
    assert "[2/7]" in launcher.stage_states[1][1]

    # Set Stage 1 to COMPLETED
    launcher.set_stage_status(
        stage_id=1,
        status=StageStatus.COMPLETED,
        detail="Environment & workspace initialized",
    )
    assert launcher.stages[1].status == StageStatus.COMPLETED
    assert launcher.active_stage_id is None
    assert launcher.stage_states[1] == ("completed", "Environment & workspace initialized")


def test_launcher_checklist_renders_sub_operations_and_no_fake_progress(tmp_path: Path):
    """Verifies checklist HTML renders real sub-operations and omits progress bar when indeterminate."""
    launcher = APEXLauncher(workspace_path=tmp_path)

    # Indeterminate running state: progress_pct is None
    launcher.set_stage_status(
        stage_id=1,
        status=StageStatus.RUNNING,
        sub_op="[4/7] Validating base runtime configuration...",
        progress_pct=None,
    )

    html_out = launcher._render_checklist_html()
    assert "1. Environment Initialization" in html_out
    assert "[4/7] Validating base runtime configuration..." in html_out
    # When progress_pct is None, there must be NO percentage bar or fake 10%, 20%
    assert "apex-progress-bar" not in html_out

    # Measurable running state: progress_pct is 42.5%
    launcher.set_stage_status(
        stage_id=5,
        status=StageStatus.RUNNING,
        sub_op="Downloading weights: 425 MB / 1000 MB",
        progress_pct=42.5,
    )
    html_measurable = launcher._render_checklist_html()
    assert "42.5%" in html_measurable
    assert "apex-progress-bar" in html_measurable
    assert "Downloading weights: 425 MB / 1000 MB" in html_measurable


# ── 3. Stall Detection Watchdog ──────────────────────────────────────────────

def test_stall_watchdog_triggers_warning_after_threshold(tmp_path: Path):
    """Verifies that the stall watchdog flags is_stalled without aborting the process."""
    launcher = APEXLauncher(workspace_path=tmp_path)
    launcher.stall_threshold_seconds = 0.2  # Fast threshold for unit test
    launcher.is_launching = True

    launcher.set_stage_status(1, StageStatus.RUNNING, detail="Testing long operation")
    launcher.active_stage_id = 1

    callback_invoked = threading.Event()
    launcher._start_stall_watchdog(on_tick=lambda: callback_invoked.set())

    # Simulate inactivity by artificially setting last_progress_time into the past
    launcher.last_progress_time = time.time() - 1.0

    # Wait for watchdog to tick
    triggered = callback_invoked.wait(timeout=2.0)
    assert triggered is True
    assert launcher.stages[1].is_stalled is True

    # Checklist HTML should now contain stall warning banner
    checklist_html = launcher._render_checklist_html()
    assert "apex-alert-stall" in checklist_html
    assert "is taking longer than expected" in checklist_html
    assert "Developer Console" in checklist_html

    # Verifies process is NOT aborted: status is still RUNNING
    assert launcher.stages[1].status == StageStatus.RUNNING

    # Resume activity: should clear stall flag
    launcher.set_stage_status(1, StageStatus.RUNNING, sub_op="Activity resumed")
    time.sleep(0.05)  # Allow watchdog loop to observe state
    assert launcher.stages[1].is_stalled is False

    launcher._stop_stall_watchdog()


# ── 4. Live Developer Console & Secret Redaction ─────────────────────────────

def test_secret_redaction_comprehensive():
    """Verifies that all tokens, keys, passwords, and secrets are redacted."""
    raw_text = (
        "Model token: hf_1234567890abcdef12345678901234567890, "
        "Authorization: Bearer secret_bearer_token_xyz_987654321, "
        "Config: api_key='sk-prod-9876543210', "
        "password = 'super_secret_password_123', "
        "tunnel_token='cf_tunnel_09876543210987654321'"
    )

    cleaned = redact_sensitive_data(raw_text)

    assert "hf_1234567890abcdef" not in cleaned
    assert "hf_●●●●[REDACTED]" in cleaned

    assert "secret_bearer_token" not in cleaned
    assert "Bearer ●●●●[REDACTED]" in cleaned

    assert "sk-prod-9876543210" not in cleaned
    assert "●●●●[REDACTED]" in cleaned

    assert "super_secret_password_123" not in cleaned
    assert "cf_tunnel_0987654321" not in cleaned


def test_log_buffer_handler_capacity_and_listeners():
    """Verifies LogBufferHandler bounded buffer capacity and reactive listener notifications."""
    handler = LogBufferHandler(capacity=5)
    test_logger = logging.getLogger("test_observability_logger")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.DEBUG)

    received_entries = []
    handler.add_listener(lambda entry: received_entries.append(entry))

    # Emit 7 logs into capacity=5 buffer
    for i in range(7):
        test_logger.info(f"Log event #{i}")

    # Listener should have received all 7 events synchronously
    assert len(received_entries) == 7
    assert received_entries[-1].message == "Log event #6"

    # But bounded buffer must strictly hold only the latest 5
    assert len(handler.entries) == 5
    assert handler.entries[0].message == "Log event #2"
    assert handler.entries[-1].message == "Log event #6"


def test_log_buffer_handler_filtering_and_export():
    """Verifies level and query filtering in LogBufferHandler."""
    handler = LogBufferHandler(capacity=50)
    test_logger = logging.getLogger("test_filter_logger")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.DEBUG)

    test_logger.debug("Debug low-level diagnostic info")
    test_logger.info("Info regular runtime message")
    test_logger.warning("Warning potential disk bottleneck")
    test_logger.error("Error connection refused on port 8000")

    # Filter by level
    errors_only = handler.get_entries(level="ERROR")
    assert len(errors_only) == 1
    assert errors_only[0].level == "ERROR"

    warnings_only = handler.get_entries(level="WARNING")
    assert len(warnings_only) == 1
    assert warnings_only[0].level == "WARNING"

    # Filter by search query
    disk_query = handler.get_entries(query="bottleneck")
    assert len(disk_query) == 1
    assert "bottleneck" in disk_query[0].message

    # Export all
    all_entries = handler.get_entries(level="ALL")
    assert len(all_entries) == 4


# ── 5. Presentation Modes (Development vs. Release) ──────────────────────────

def test_presentation_modes_toggle(tmp_path: Path):
    """Verifies default Development Mode and switching between Development and Release modes."""
    launcher = APEXLauncher(workspace_path=tmp_path)

    # Default is development mode
    assert launcher.console_mode == "development"

    # Switch to release mode
    launcher.console_mode = "release"
    assert launcher.console_mode == "release"


def test_developer_console_html_rendering(tmp_path: Path):
    """Verifies developer console HTML format with badges and escaping."""
    launcher = APEXLauncher(workspace_path=tmp_path)

    test_logger = logging.getLogger("runtime.lifecycle")
    test_logger.info("Lifecycle test event with <script>alert(1)</script> & credentials hf_1234567890abcdef1234567890")

    console_html = launcher._render_console_logs_html()
    assert "apex-badge-log-info" in console_html
    assert "runtime.lifecycle" in console_html
    # Message should be HTML-escaped and secrets redacted
    assert "&lt;script&gt;" in console_html
    assert "hf_●●●●[REDACTED]" in console_html


# ── 6. Stage 1 Granular Sub-Operation Emission in Startup Pipeline ───────────

def test_lifecycle_startup_emits_granular_sub_operations(tmp_path: Path):
    """Verifies that RuntimeLifecycle.startup emits granular sub-operations via on_progress."""
    emitted_ops = []

    lifecycle = RuntimeLifecycle(workspace_path=tmp_path)
    ok = lifecycle.startup(interactive=False, on_progress=lambda msg: emitted_ops.append(msg))

    assert ok is True
    # Verify sub-operation markers emitted
    assert any("[1/7] Detecting runtime environment" in op for op in emitted_ops)
    assert any("[2/7] Verifying persistent storage" in op for op in emitted_ops)
    assert any("[3/7] Resolving workspace and project directories" in op for op in emitted_ops)
    assert any("[4/7] Validating runtime configuration" in op for op in emitted_ops)
    assert any("[5/7] Initializing runtime logging infrastructure" in op for op in emitted_ops)
    assert any("[6/7] Validating filesystem directory permissions" in op for op in emitted_ops)
    assert any("[7/7] Loading project identity" in op for op in emitted_ops)


# ── 7. Pipeline Failure Handling & Cancellation ──────────────────────────────

def test_pipeline_failure_cancels_subsequent_stages_and_enables_retry(tmp_path: Path):
    """Verifies that failure in Stage 1 marks it FAILED, cancels remaining stages, and allows retry."""
    launcher = APEXLauncher(workspace_path=tmp_path)

    completion_event = threading.Event()
    results = []

    # Mock lifecycle.startup to fail
    with patch.object(RuntimeLifecycle, "startup", return_value=False):
        launcher.launch(
            on_complete=lambda ok, err: (results.append((ok, err)), completion_event.set())
        )
        assert completion_event.wait(timeout=3.0) is True

    assert len(results) == 1
    success, err_msg = results[0]
    assert success is False
    assert "Runtime environment initialization failed" in err_msg

    # Stage 1 must be FAILED
    assert launcher.stages[1].status == StageStatus.FAILED
    assert launcher.stages[1].error is not None

    # Subsequent stages must be CANCELLED (not left in pending or stuck in running)
    for sid in range(2, 11):
        assert launcher.stages[sid].status == StageStatus.CANCELLED

    # Launcher is no longer launching
    assert launcher.is_launching is False


# ── 8. Acceptance Verification: Build ID, Storage, & Indeterminate Activity ──

def test_build_identifier_exposure_and_rendering(tmp_path: Path):
    """Verifies that non-secret development build identifier is exposed and rendered in dashboard."""
    from runtime.ui.launcher import APEX_BUILD_ID, APEXLauncher

    assert isinstance(APEX_BUILD_ID, str)
    assert len(APEX_BUILD_ID) > 5
    assert APEXLauncher.BUILD_ID == APEX_BUILD_ID

    launcher = APEXLauncher(workspace_path=tmp_path)
    hw_html = launcher._render_hardware_html()
    assert APEX_BUILD_ID in hw_html
    assert "apex-build-badge" in hw_html

    console_html = launcher._render_console_logs_html()
    assert APEX_BUILD_ID in console_html


def test_drive_manager_persistence_status_and_explicit_fallback(tmp_path: Path):
    """Verifies DriveManager distinguishes persistent vs ephemeral storage and logs explicit fallbacks."""
    from runtime.drive.manager import DriveManager

    dm = DriveManager(fallback_local_root=tmp_path)
    # On local non-colab environment
    assert dm.is_colab_env is False
    assert dm.mount() is True
    assert dm.is_using_persistent_storage is True

    # In Colab simulation
    dm.is_colab_env = True
    # Background thread mount must fail safely and explicitly fall back
    with patch("threading.current_thread") as mock_thread:
        mock_thread.return_value = threading.Thread(name="BackgroundWorkerTest")
        result = dm.mount()
        assert result is False
        assert dm.persistence_root == dm.project_root
        assert dm.is_using_persistent_storage is False


def test_indeterminate_progress_vs_determinate_rendering(tmp_path: Path):
    """Verifies indeterminate shimmer bar is used when progress is non-measurable, avoiding fake curves."""
    launcher = APEXLauncher(workspace_path=tmp_path)

    # Indeterminate stage
    launcher.set_stage_status(
        stage_id=6,
        status=StageStatus.RUNNING,
        detail="Loading tensors into memory...",
        sub_op="Allocating 1.5 GB tensors...",
        progress_pct=None,
    )

    html_out = launcher._render_checklist_html()
    assert "apex-indeterminate-bar" in html_out
    assert "apex-progress-bar" not in html_out
    assert "Stage 6/10" in html_out
    assert "Allocating 1.5 GB tensors..." in html_out
    assert "Last progress event:" in html_out

    # Measurable stage (e.g. download bytes)
    launcher.set_stage_status(
        stage_id=6,
        status=StageStatus.RUNNING,
        detail="Loading tensors...",
        sub_op="Loaded 750 MB / 1500 MB",
        progress_pct=50.0,
    )

    html_meas = launcher._render_checklist_html()
    assert "apex-progress-bar" in html_meas
    assert "50.0%" in html_meas
    assert "Loaded 750 MB / 1500 MB" in html_meas
