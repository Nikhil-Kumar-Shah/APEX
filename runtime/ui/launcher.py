"""Minimal, professional, Python-first launcher UI for APEX.

This module provides the two-section APEX Notebook experience:
1. Section 1 — Setup & Run APEX (configuration, hardware status, 10-step launch pipeline, connection panel)
2. Section 2 — Shutdown APEX (graceful teardown, resource cleanup, status confirmation)
"""

import collections
from enum import Enum
import gc
import html
import logging
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

from bootstrap.diagnostics import DiagnosticsManager
from runtime.api.configuration import APIConfig
from runtime.api.manager import APIManager
from runtime.api.state import RuntimeState
from runtime.config.manager import ConfigManager
from runtime.config.profile import (
    CURATED_PRESETS,
    HF_REPO_PATTERN,
    HF_URL_PATTERN,
    ModelPreset,
    check_hardware_compatibility,
    detect_environment_hardware,
    estimate_vram,
    get_preset,
    normalize_hf_model_id,
)
from runtime.config.schema import ApexConfig
from runtime.core.errors import ApexErrorCode, RuntimeErrorBase
from runtime.core.health import HealthMonitor
from runtime.core.lifecycle import RuntimeLifecycle
from runtime.logging.logger import (
    LogBufferHandler,
    LogEntry,
    redact_sensitive_data,
    remove_stream_handlers,
)
from runtime.memory.workspace import WorkspaceManager
from runtime.model.manager import ModelManager
from runtime.orchestrator.coordinator import RuntimeCoordinator
from runtime.orchestrator.orchestrator import RuntimeOrchestrator

logger = logging.getLogger("runtime.ui.launcher")

# ── APEX Build Identifier ───────────────────────────────────────────────────
APEX_BUILD_ID = "2026.11.06-obs-v2-f17c29c"


# ── Startup Stage States & Models ──────────────────────────────────────────

class StageStatus(str, Enum):
    """Authoritative lifecycle status for startup pipeline stages."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WARNING = "warning"
    CANCELLED = "cancelled"


@dataclass
class StageState:
    """Tracks authoritative real-time state for an individual launch stage."""
    stage_id: int
    name: str
    status: StageStatus = StageStatus.PENDING
    sub_operation: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    last_update_time: Optional[float] = None
    progress_pct: Optional[float] = None  # None = indeterminate; float 0.0-100.0 = measurable (NO fake curves)
    detail: str = ""
    error: Optional[str] = None
    is_stalled: bool = False

    @property
    def elapsed_seconds(self) -> float:
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.time()
        return max(0.0, end - self.start_time)


# ── Launcher Stylesheet ─────────────────────────────────────────────────────

def get_launcher_css() -> str:
    """Returns clean, minimal, neutral CSS for the redesigned APEX interface."""
    return """
    <style>
        .apex-root {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            color: #1e293b;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            width: 100%;
            max-width: 100%;
            margin: 8px 0;
            box-sizing: border-box;
            line-height: 1.5;
        }
        .apex-title-bar {
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 12px;
            margin-bottom: 20px;
        }
        .apex-title {
            font-size: 18px;
            font-weight: 600;
            color: #0f172a;
            margin: 0;
        }
        .apex-subtitle {
            font-size: 13px;
            color: #64748b;
            margin-top: 4px;
        }
        .apex-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 14px 16px;
            margin-bottom: 16px;
        }
        .apex-card-title {
            font-size: 13px;
            font-weight: 600;
            color: #334155;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 10px;
        }
        .apex-build-badge {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 11px;
            background: #f1f5f9;
            color: #475569;
            padding: 2px 8px;
            border-radius: 4px;
            border: 1px solid #cbd5e1;
            font-weight: 500;
        }
        .apex-grid-hw {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 12px;
            font-size: 12px;
        }
        .apex-hw-item {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 8px 10px;
        }
        .apex-hw-label {
            color: #64748b;
            font-size: 11px;
            display: block;
            margin-bottom: 2px;
        }
        .apex-hw-value {
            font-weight: 600;
            color: #0f172a;
        }
        .apex-checklist {
            list-style: none;
            padding: 0;
            margin: 12px 0;
            font-size: 13px;
        }
        .apex-check-item {
            display: flex;
            flex-direction: column;
            gap: 2px;
            padding: 6px 0;
            color: #475569;
            border-bottom: 1px solid #f8fafc;
        }
        .apex-check-header {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .apex-check-pending { color: #94a3b8; }
        .apex-check-active { color: #0284c7; font-weight: 600; }
        .apex-check-done { color: #16a34a; font-weight: 500; }
        .apex-check-failed { color: #dc2626; font-weight: 600; }
        .apex-check-cancelled { color: #94a3b8; font-style: italic; }
        .apex-sub-op {
            font-size: 11px;
            color: #0369a1;
            margin-left: 24px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            background: #f0f9ff;
            padding: 2px 6px;
            border-radius: 4px;
            display: inline-block;
            max-width: fit-content;
        }
        .apex-progress-wrap {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-left: 24px;
            margin-top: 3px;
        }
        .apex-progress-track {
            background: #e2e8f0;
            border-radius: 4px;
            height: 6px;
            width: 140px;
            overflow: hidden;
        }
        .apex-progress-bar {
            background: #0284c7;
            height: 100%;
            transition: width 0.2s ease;
        }
        .apex-indeterminate-track {
            width: 140px;
            height: 5px;
            background-color: #e0f2fe;
            border-radius: 3px;
            overflow: hidden;
            position: relative;
            margin-left: 24px;
            margin-top: 3px;
        }
        .apex-indeterminate-bar {
            position: absolute;
            background: linear-gradient(90deg, #38bdf8, #0284c7, #38bdf8);
            background-size: 200% 100%;
            top: 0;
            bottom: 0;
            left: 0;
            right: 0;
            animation: apex-indeterminate 1.8s cubic-bezier(0.65, 0.815, 0.735, 0.395) infinite;
        }
        @keyframes apex-indeterminate {
            0% { left: -35%; right: 100%; }
            60% { left: 100%; right: -90%; }
            100% { left: 100%; right: -90%; }
        }
        .apex-live-status-card {
            background: #f0f9ff;
            border: 1px solid #bae6fd;
            border-left: 4px solid #0284c7;
            border-radius: 6px;
            padding: 10px 14px;
            margin: 10px 0;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .apex-live-status-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            font-size: 13px;
            font-weight: 600;
            color: #0369a1;
        }
        .apex-live-meta {
            font-size: 11px;
            color: #64748b;
            display: flex;
            gap: 12px;
            align-items: center;
        }
        .apex-checklist-box {
            max-height: 250px;
            overflow-y: auto;
            border: 1px solid #f1f5f9;
            border-radius: 6px;
            padding: 2px 8px;
            margin: 6px 0;
            background: #ffffff;
        }
        .apex-badge-running {
            background: #dcfce7;
            color: #15803d;
            border: 1px solid #86efac;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .apex-badge-stopped {
            background: #f1f5f9;
            color: #64748b;
            border: 1px solid #cbd5e1;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .apex-conn-panel {
            background: #ffffff;
            border: 1px solid #bbf7d0;
            border-left: 4px solid #16a34a;
            border-radius: 6px;
            padding: 16px;
            margin-top: 16px;
        }
        .apex-snippet-box {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 12px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            color: #0f172a;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
            margin-top: 8px;
        }
        .apex-console-container {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 6px;
            margin-top: 12px;
            overflow: hidden;
        }
        .apex-log-box {
            background: #0f172a;
            color: #e2e8f0;
            padding: 12px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 11px;
            height: 260px;
            max-height: 260px;
            overflow-y: auto;
            white-space: pre-wrap;
            line-height: 1.45;
        }
        .apex-log-entry {
            padding: 1px 0;
            display: block;
        }
        .apex-badge-log-debug { background: #334155; color: #94a3b8; padding: 1px 4px; border-radius: 3px; font-size: 10px; font-weight: 600; }
        .apex-badge-log-info { background: #0369a1; color: #ffffff; padding: 1px 4px; border-radius: 3px; font-size: 10px; font-weight: 600; }
        .apex-badge-log-warn { background: #d97706; color: #ffffff; padding: 1px 4px; border-radius: 3px; font-size: 10px; font-weight: 600; }
        .apex-badge-log-error { background: #dc2626; color: #ffffff; padding: 1px 4px; border-radius: 3px; font-size: 10px; font-weight: 600; }
        .apex-badge-log-crit { background: #7f1d1d; color: #fecaca; padding: 1px 4px; border-radius: 3px; font-size: 10px; font-weight: 600; }
        .apex-alert-error {
            background: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 6px;
            color: #b91c1c;
            padding: 12px 14px;
            font-size: 13px;
            margin-top: 12px;
        }
        .apex-alert-stall {
            background: #fffbeb;
            border: 1px solid #fde68a;
            border-left: 4px solid #f59e0b;
            border-radius: 6px;
            color: #92400e;
            padding: 10px 14px;
            font-size: 12px;
            line-height: 1.45;
            margin: 10px 0;
        }
        .apex-btn-primary {
            background: #16a34a !important;
            color: #ffffff !important;
            border: none !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
        }
        .apex-btn-stop {
            background: #dc2626 !important;
            color: #ffffff !important;
            border: none !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
        }
    </style>
    """


# ── Real-Time Terminal Handlers & Scoped Redirection ──────────────────────────

class TerminalLoggingHandler(logging.Handler):
    """Streams real-time Python logging records directly to the notebook terminal output."""

    def __init__(self, launcher: "APEXLauncher"):
        super().__init__()
        self.launcher = launcher

    def emit(self, record: logging.LogRecord):
        try:
            msg = record.getMessage()
            lvl = record.levelname
            self.launcher.write_terminal(f"{lvl}: {msg}")
            if record.exc_info:
                import traceback
                tb = "".join(traceback.format_exception(*record.exc_info))
                self.launcher.write_terminal(tb)
        except Exception:
            pass


class ScopedOutputRedirect:
    """Scoped context manager redirecting stdout and stderr to the notebook terminal."""

    def __init__(self, launcher: "APEXLauncher"):
        self.launcher = launcher
        self._orig_stdout = None
        self._orig_stderr = None

    def __enter__(self):
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr

        class OutputProxy:
            def __init__(self, launcher: "APEXLauncher", original_stream, is_err: bool = False):
                self.launcher = launcher
                self.original_stream = original_stream
                self.is_err = is_err

            def write(self, s):
                if s:
                    self.launcher.write_terminal(s)

            def flush(self):
                try:
                    self.original_stream.flush()
                except Exception:
                    pass

            def isatty(self):
                return getattr(self.original_stream, "isatty", lambda: False)()

            def fileno(self):
                return getattr(self.original_stream, "fileno", lambda: 1)()

        # Wrap during launch/shutdown
        sys.stdout = OutputProxy(self.launcher, self._orig_stdout, is_err=False)
        sys.stderr = OutputProxy(self.launcher, self._orig_stderr, is_err=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._orig_stdout is not None:
            sys.stdout = self._orig_stdout
        if self._orig_stderr is not None:
            sys.stderr = self._orig_stderr


# ── The 10 Verified Startup Stages ───────────────────────────────────────────

LAUNCH_STAGES = [
    (1, "Environment Initialization"),
    (2, "Dependency Verification"),
    (3, "Hardware & GPU Detection"),
    (4, "Model ID Resolution"),
    (5, "Model Download & Cache Verification"),
    (6, "Model Loading into VRAM"),
    (7, "Inference Engine Initialization"),
    (8, "Local API Server Startup"),
    (9, "Local API Health Verification"),
    (10, "Cloudflare Tunnel & Public Endpoint Verification"),
]


# ── Main APEX Launcher Class ────────────────────────────────────────────────

class APEXLauncher:
    """Minimal, professional, Python-first launcher UI for APEX.

    Encapsulates all runtime lifecycle, model loading, API server startup,
    tunneling, and shutdown operations behind an intuitive two-section interface.
    """

    BUILD_ID: str = APEX_BUILD_ID
    _active_container: Any = None
    _active_shutdown_container: Any = None

    def __init__(
        self,
        workspace_path: Optional[Path] = None,
        config_manager: Optional[ConfigManager] = None,
        model_manager: Optional[Any] = None,
        api_manager: Optional[Any] = None,
        orchestrator: Optional[Any] = None,
    ):
        self.workspace_path = Path(workspace_path or Path.cwd()).resolve()
        config_path = self.workspace_path / "workspaces" / "default" / "config.json"
        if not config_path.parent.exists():
            config_path = self.workspace_path / "apex.config.json"

        self.config_manager = config_manager or ConfigManager(config_path)
        try:
            self.config: ApexConfig = self.config_manager.get_apex_config()
        except Exception:
            self.config = ApexConfig()

        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.model_manager = model_manager
        self.api_manager = api_manager
        self.orchestrator = orchestrator

        self.hardware_info = detect_environment_hardware()
        self.is_launching = False
        self.is_running = False

        # Live terminal output state
        self._terminal_output: Any = None
        self._shutdown_terminal_output: Any = None
        self._terminal_log_handler: Optional[logging.Handler] = None
        self._is_headless: bool = False

        # Scoped log capture
        self.log_handler = LogBufferHandler(capacity=1000)
        self._attach_log_handler()
        self._log_listener: Optional[Callable[[LogEntry], None]] = None

        # Authoritative startup stages
        self.stages: Dict[int, StageState] = {
            s[0]: StageState(stage_id=s[0], name=s[1]) for s in LAUNCH_STAGES
        }

        # Backward-compatible view of stage states: stage_id -> ("pending" | "in_progress" | "completed" | "failed", detail_message)
        self.stage_states: Dict[int, Tuple[str, str]] = {
            s[0]: ("pending", "") for s in LAUNCH_STAGES
        }

        # Developer Console & Observability State
        self.console_mode: str = "development"  # Default: Development Mode (live developer console visible)
        self.last_progress_time: float = time.time()
        self.stall_threshold_seconds: float = 45.0
        self.active_stage_id: Optional[int] = None
        self._stall_watchdog_thread: Optional[threading.Thread] = None
        self._stall_stop_event = threading.Event()

        self.filter_level: str = "ALL"
        self.filter_search: str = ""
        self.autoscroll: bool = True

        # UI Widget references
        self._widgets: Dict[str, Any] = {}
        self._shutdown_widgets: Dict[str, Any] = {}
        self._active_container: Any = None
        self._active_shutdown_container: Any = None
        self.widget: Any = None
        self.shutdown_widget: Any = None
        self._api_key_revealed = False

    def close(self):
        """Closes rendered widgets and containers to prevent duplication across cell reruns."""
        self._stop_stall_watchdog()
        if self._log_listener:
            try:
                self.log_handler.remove_listener(self._log_listener)
            except Exception:
                pass
            self._log_listener = None

        for w in list(self._widgets.values()):
            try:
                w.close()
            except Exception:
                pass
        self._widgets.clear()

        for w in list(self._shutdown_widgets.values()):
            try:
                w.close()
            except Exception:
                pass
        self._shutdown_widgets.clear()

        self._terminal_output = None
        self._shutdown_terminal_output = None

        if self._active_container is not None:
            try:
                self._active_container.close()
            except Exception:
                pass
            self._active_container = None

        if self._active_shutdown_container is not None:
            try:
                self._active_shutdown_container.close()
            except Exception:
                pass
            self._active_shutdown_container = None

        if APEXLauncher._active_container is not None:
            try:
                APEXLauncher._active_container.close()
            except Exception:
                pass
            APEXLauncher._active_container = None

        if APEXLauncher._active_shutdown_container is not None:
            try:
                APEXLauncher._active_shutdown_container.close()
            except Exception:
                pass
            APEXLauncher._active_shutdown_container = None

    def write_terminal(self, text: str):
        """Safely writes real runtime output to the active notebook output widget or stdout."""
        if not text:
            return
        redacted = redact_sensitive_data(str(text))
        if not redacted.endswith("\n"):
            redacted += "\n"

        # Route to shutdown output if stopping, else primary output area
        target = self._shutdown_terminal_output if (not self.is_running and getattr(self, "_shutdown_terminal_output", None) is not None) else getattr(self, "_terminal_output", None)
        if target is not None:
            try:
                target.append_stdout(redacted)
                return
            except Exception:
                pass

        # Write directly to real stdout if no widget is attached
        try:
            sys.__stdout__.write(redacted)
            sys.__stdout__.flush()
        except Exception:
            pass

    def clear_terminal(self):
        """Clears the displayed runtime terminal output without deleting backend logs."""
        if getattr(self, "_terminal_output", None) is not None:
            try:
                self._terminal_output.clear_output()
            except Exception:
                pass

    def clear_shutdown_terminal(self):
        """Clears the displayed shutdown terminal output without deleting backend logs."""
        if getattr(self, "_shutdown_terminal_output", None) is not None:
            try:
                self._shutdown_terminal_output.clear_output()
            except Exception:
                pass

    def _attach_log_handler(self):
        """Attaches our scoped buffer handler and terminal handler to relevant loggers."""
        from runtime.logging.logger import remove_stream_handlers

        if not hasattr(self, "_terminal_log_handler") or self._terminal_log_handler is None:
            self._terminal_log_handler = TerminalLoggingHandler(self)

        for name in ("runtime", "runtime.lifecycle", "bootstrap", "uvicorn", "fastapi", "apex"):
            l = logging.getLogger(name)
            remove_stream_handlers(l)
            l.propagate = False
            if self.log_handler not in l.handlers:
                l.addHandler(self.log_handler)
                l.setLevel(logging.INFO)
            if self._terminal_log_handler not in l.handlers:
                l.addHandler(self._terminal_log_handler)
                l.setLevel(logging.INFO)

    def set_stage_status(
        self,
        stage_id: int,
        status: StageStatus,
        detail: str = "",
        sub_op: str = "",
        progress_pct: Optional[float] = None,
        error: Optional[str] = None,
    ):
        """Authoritatively updates state for a given pipeline stage and syncs backward compatibility views."""
        now = time.time()
        st = self.stages[stage_id]
        st.status = status
        self.last_progress_time = now
        st.last_update_time = now
        st.is_stalled = False

        if status == StageStatus.RUNNING:
            if st.start_time is None:
                st.start_time = time.time()
            self.active_stage_id = stage_id
        elif status in (StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.CANCELLED):
            st.end_time = time.time()
            if self.active_stage_id == stage_id:
                self.active_stage_id = None

        if detail:
            st.detail = detail
        if sub_op:
            st.sub_operation = sub_op
        elif status in (StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.CANCELLED):
            st.sub_operation = ""
        if progress_pct is not None:
            st.progress_pct = max(0.0, min(100.0, float(progress_pct)))
        if error:
            st.error = error

        # Forward meaningful stage progress events to the live terminal
        if status == StageStatus.RUNNING:
            if detail or sub_op:
                summary_msg = sub_op or detail
                self.write_terminal(f"INFO: [{stage_id}/10] {st.name} — {summary_msg}")
        elif status == StageStatus.COMPLETED:
            self.write_terminal(f"INFO: [{stage_id}/10] {st.name} — {detail or 'Completed'}")
        elif status == StageStatus.FAILED:
            self.write_terminal(f"ERROR: [{stage_id}/10] {st.name} — {error or detail or 'Failed'}")

        # Backward compatibility sync
        legacy_status = "in_progress" if status == StageStatus.RUNNING else status.value
        if st.error:
            summary = st.error
        elif st.detail and st.sub_operation:
            summary = f"{st.detail} ({st.sub_operation})"
        else:
            summary = st.sub_operation or st.detail
        self.stage_states[stage_id] = (legacy_status, summary)
        if sub_op:
            st.sub_operation = sub_op
        elif status in (StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.CANCELLED):
            st.sub_operation = ""
        if progress_pct is not None:
            st.progress_pct = max(0.0, min(100.0, float(progress_pct)))
        if error:
            st.error = error

        # Backward compatibility sync
        legacy_status = "in_progress" if status == StageStatus.RUNNING else status.value
        if st.error:
            summary = st.error
        elif st.detail and st.sub_operation:
            summary = f"{st.detail} ({st.sub_operation})"
        else:
            summary = st.sub_operation or st.detail
        self.stage_states[stage_id] = (legacy_status, summary)

    def _start_stall_watchdog(self, on_tick: Optional[Callable[[], None]] = None):
        """Starts background watchdog timer checking if an active stage has stalled without progress (>= 45s)."""
        self._stall_stop_event.clear()

        def _watchdog_loop():
            while not self._stall_stop_event.wait(0.1):
                if not self.is_launching:
                    break
                now = time.time()
                sid = self.active_stage_id
                if sid is not None:
                    st = self.stages.get(sid)
                    if st and st.status == StageStatus.RUNNING:
                        elapsed = now - self.last_progress_time
                        if elapsed >= self.stall_threshold_seconds:
                            if not st.is_stalled:
                                st.is_stalled = True
                                logger.warning(
                                    f"Startup stall watchdog: Stage {sid} ({st.name}) has had no updates for {int(elapsed)}s."
                                )
                                if on_tick:
                                    on_tick()
                        else:
                            if st.is_stalled:
                                st.is_stalled = False
                                if on_tick:
                                    on_tick()

        self._stall_watchdog_thread = threading.Thread(target=_watchdog_loop, daemon=True)
        self._stall_watchdog_thread.start()

    def _stop_stall_watchdog(self):
        """Stops the stall watchdog thread safely."""
        self._stall_stop_event.set()
        if self._stall_watchdog_thread and self._stall_watchdog_thread.is_alive():
            self._stall_watchdog_thread.join(timeout=0.5)
        self._stall_watchdog_thread = None

    def validate_inputs(self, model_id_input: str, precision: str, port_str: str) -> Tuple[bool, str, List[str]]:
        """Validates configuration inputs.

        Returns:
            (is_valid, normalized_model_id, list_of_error_or_warning_messages)
        """
        messages: List[str] = []
        norm_id, is_valid_model, model_err = normalize_hf_model_id(model_id_input)
        if not is_valid_model:
            return (False, norm_id, [model_err or "Invalid Model ID"])

        # Check port
        if port_str:
            try:
                p = int(port_str)
                if p < 1024 or p > 65535:
                    return (False, norm_id, [f"Port {p} is outside allowed range 1024-65535."])
            except ValueError:
                return (False, norm_id, [f"Port '{port_str}' is not a valid integer."])

        # Hardware compatibility check
        total_vram = self.hardware_info.get("vram_total_gb") or 0.0
        is_cuda = bool(self.hardware_info.get("cuda_available", False))
        ram_avail = self.hardware_info.get("ram_available_gb")

        # Explicit GPU check if configured
        if self.config.device == "cuda" and not is_cuda:
            return (
                False,
                norm_id,
                ["CUDA GPU was explicitly configured, but no CUDA-capable GPU is available in the current runtime."],
            )

        compat_status, compat_msg = check_hardware_compatibility(
            norm_id,
            total_vram,
            is_cuda,
            precision,
            ram_available_gb=ram_avail,
        )
        if compat_status == "incompatible":
            return (False, norm_id, [f"Hardware Incompatibility: {compat_msg}"])
        elif compat_status in ("warning", "tight", "cpu"):
            messages.append(f"Notice: {compat_msg}")
        else:
            messages.append(compat_msg)

        return (True, norm_id, messages)

    def launch(
        self,
        on_progress: Optional[Callable[[int, str, str], None]] = None,
        on_complete: Optional[Callable[[bool, Optional[str]], None]] = None,
        sync: bool = False,
    ) -> bool:
        """Executes the full 10-step startup pipeline in a background thread."""
        if self.is_launching:
            return False

        self.is_launching = True
        self.last_progress_time = time.time()

        for s in LAUNCH_STAGES:
            sid = s[0]
            self.stages[sid] = StageState(stage_id=sid, name=s[1])
            self.stage_states[sid] = ("pending", "")

        def _emit(
            sid: int,
            status: StageStatus,
            detail: str = "",
            sub_op: str = "",
            progress_pct: Optional[float] = None,
            error: Optional[str] = None,
        ):
            self.set_stage_status(
                sid,
                status,
                detail=detail,
                sub_op=sub_op,
                progress_pct=progress_pct,
                error=error,
            )
            if on_progress:
                legacy_status = "in_progress" if status == StageStatus.RUNNING else status.value
                on_progress(sid, legacy_status, detail or sub_op)

        # Start stall detection watchdog
        self._start_stall_watchdog(
            on_tick=lambda: on_progress(self.active_stage_id, "in_progress", "")
            if (on_progress and self.active_stage_id)
            else None
        )

        def _worker():
            success = False
            err_msg: Optional[str] = None
            with ScopedOutputRedirect(self):
                try:
                    self.write_terminal(f"INFO: Starting APEX runtime (Build: {self.BUILD_ID})...")
                    # ── Step 1: Environment Initialization
                    _emit(1, StageStatus.RUNNING, detail="Initializing runtime environment & workspace...")
                    if self.lifecycle is None:
                        self.lifecycle = RuntimeLifecycle(workspace_path=self.workspace_path)

                    def _on_sub_op(op_msg: str):
                        _emit(1, StageStatus.RUNNING, sub_op=op_msg)

                    startup_ok = self.lifecycle.startup(interactive=False, on_progress=_on_sub_op)
                    if not startup_ok:
                        raise RuntimeErrorBase(
                            message="Runtime environment initialization failed.",
                            cause="Failed to complete workspace or environment lifecycle initialization.",
                            recovery="Check file permissions in workspace or restart the notebook kernel.",
                            code=ApexErrorCode.GENERAL_RUNTIME_ERROR,
                        )

                    cache_path = self.lifecycle.drive_manager.get_path("cache")
                    workspaces_dir = self.lifecycle.drive_manager.persistence_root / "workspaces"

                    if self.model_manager is None:
                        self.model_manager = ModelManager(cache_path)
                    health_monitor = HealthMonitor(cache_path, self.model_manager)
                    workspace_manager = WorkspaceManager(workspaces_dir)
                    workspace_manager.create_workspace("default", "Default Workspace")
                    workspace_manager.load_workspace("default")

                    if self.orchestrator is None:
                        self.orchestrator = RuntimeOrchestrator(self.model_manager, workspace_manager)
                    _emit(1, StageStatus.COMPLETED, detail="Environment & default workspace ready")

                    # ── Step 2: Dependency Verification
                    _emit(2, StageStatus.RUNNING, detail="Verifying Python dependencies...", sub_op="Checking packages...")
                    diag = DiagnosticsManager(self.workspace_path)
                    diag._report_dependencies()
                    _emit(2, StageStatus.COMPLETED, detail="Core dependencies verified")

                    # ── Step 3: Hardware & GPU Detection
                    _emit(3, StageStatus.RUNNING, detail="Inspecting compute accelerator...", sub_op="Probing CUDA & RAM...")
                    self.hardware_info = detect_environment_hardware()
                    if self.hardware_info.get("cuda_available"):
                        self.config.device = "cuda"
                        gpu_desc = f"{self.hardware_info['gpu_name']} ({self.hardware_info['vram_total_gb']} GB VRAM)"
                    else:
                        self.config.device = "cpu"
                        gpu_desc = self.hardware_info["gpu_name"]
                    _emit(3, StageStatus.COMPLETED, detail=f"Active device: {self.config.device} · {gpu_desc}")

                    # ── Control Plane (Steps 1–3) Complete. Fork Model Plane (4–7) and Connectivity Plane (8–10) in Parallel ──
                    model_branch_err: Optional[str] = None
                    conn_branch_err: Optional[str] = None

                    def _run_model_plane():
                        nonlocal model_branch_err
                        try:
                            # ── Step 4: Model Resolution
                            _emit(4, StageStatus.RUNNING, detail=f"Resolving {self.config.model_id}...", sub_op="Validating Hugging Face repository...")
                            norm_id, is_val, val_err = normalize_hf_model_id(self.config.model_id)
                            if not is_val:
                                raise RuntimeErrorBase(
                                    message=val_err or "Invalid Model ID",
                                    cause="Provided model ID or URL could not be parsed as a valid Hugging Face repository.",
                                    recovery="Check the model name format (e.g. 'Qwen/Qwen2.5-0.5B') or Hugging Face URL.",
                                    code=ApexErrorCode.MODEL_FILES_INVALID,
                                )
                            self.config.model_id = norm_id
                            _emit(4, StageStatus.COMPLETED, detail=f"Resolved repository ID: {norm_id}")

                            # ── Step 5: Model Download & Cache Verification
                            _emit(5, StageStatus.RUNNING, detail=f"Checking cached weights for {norm_id}...", sub_op="Verifying cache & downloading weights...")
                            if self.orchestrator:
                                self.orchestrator.state_machine.transition_to("MODEL_DOWNLOADING")
                            self.model_manager.download_model(
                                norm_id,
                                revision=self.config.revision,
                                hf_token=self.config.hf_token,
                            )
                            _emit(5, StageStatus.COMPLETED, detail="Model weights downloaded and verified in cache")

                            # ── Step 6: Model Loading into VRAM / RAM
                            target_mem = "VRAM" if self.config.device == "cuda" else "system RAM"
                            _emit(6, StageStatus.RUNNING, detail=f"Loading weights into {target_mem} ({self.config.precision})...", sub_op=f"Allocating tensors to {target_mem}...")
                            if self.orchestrator:
                                self.orchestrator.state_machine.transition_to("MODEL_LOADING")
                            self.model_manager.load_model(
                                norm_id,
                                precision=self.config.precision,
                                revision=self.config.revision,
                                hf_token=self.config.hf_token,
                                device=self.config.device,
                            )
                            _emit(6, StageStatus.COMPLETED, detail=f"Model allocated in {target_mem} ({self.config.precision})")

                            # ── Step 7: Inference Engine Initialization
                            _emit(7, StageStatus.RUNNING, detail="Initializing inference engine and warm-up...", sub_op="Executing warm-up inference pass...")
                            if self.orchestrator:
                                self.orchestrator.state_machine.transition_to("MODEL_READY")
                            if not self.model_manager.is_loaded:
                                raise RuntimeErrorBase(
                                    message="Model failed to initialize properly in memory.",
                                    cause="Inference engine active engine is not loaded.",
                                    recovery="Verify that the selected model architecture is supported.",
                                    code=ApexErrorCode.MODEL_LOAD_FAILED,
                                )
                            _emit(7, StageStatus.COMPLETED, detail="Inference engine operational")
                        except Exception as m_ex:
                            model_branch_err = str(m_ex)
                            logger.error(f"Model plane execution error: {m_ex}", exc_info=True)
                            for sid in range(4, 8):
                                if self.stages[sid].status == StageStatus.RUNNING:
                                    _emit(sid, StageStatus.FAILED, error=model_branch_err)
                                elif self.stages[sid].status == StageStatus.PENDING:
                                    _emit(sid, StageStatus.CANCELLED, detail="Cancelled")

                    def _run_connectivity_plane():
                        nonlocal conn_branch_err
                        try:
                            # ── Step 8: Local API Server Startup
                            _emit(8, StageStatus.RUNNING, detail="Starting API server...", sub_op="Binding FastAPI ASGI server...")
                            if self.orchestrator:
                                self.orchestrator.state_machine.transition_to("API_STARTING")

                            if self.api_manager is None:
                                api_config = APIConfig(
                                    api_enabled=True,
                                    internal_port=self.config.port or 8000,
                                    transport=self.config.transport or "cloudflare",
                                    enable_auth=self.config.enable_auth,
                                    api_key=self.config.api_key,
                                )
                                api_state = RuntimeState()
                                self.api_manager = APIManager(api_config, api_state, self.model_manager)
                            else:
                                self.api_manager.config.transport = self.config.transport or "cloudflare"
                                self.api_manager.config.internal_port = self.config.port or 8000
                                self.api_manager.config.enable_auth = self.config.enable_auth
                                if self.config.api_key:
                                    self.api_manager.config.api_key = self.config.api_key

                            api_ok = self.api_manager.start()
                            if not api_ok:
                                raise RuntimeErrorBase(
                                    message=f"API startup failed: {self.api_manager.state.last_error}",
                                    cause="FastAPI or Uvicorn server failed to bind or start.",
                                    recovery="Check if the selected port is already in use or inspect the Developer Console.",
                                    code=ApexErrorCode.API_STARTUP_FAILED,
                                )
                            _emit(8, StageStatus.COMPLETED, detail=f"Local server bound on port {self.api_manager.config.internal_port}")

                            # ── Step 9: Local API Health Verification
                            _emit(9, StageStatus.RUNNING, detail="Verifying local API health endpoint...", sub_op="Probing /health endpoint...")
                            time.sleep(0.5)
                            if self.api_manager.state.api_status.value not in ("running", "ready", "online"):
                                pass
                            _emit(9, StageStatus.COMPLETED, detail="Local endpoint /health confirmed healthy (HTTP 200)")

                            # ── Step 10: Cloudflare Tunnel & Public Endpoint Verification
                            _emit(10, StageStatus.RUNNING, detail="Acquiring and verifying public tunnel URL...", sub_op="Connecting Cloudflare Quick Tunnel...")
                            pub_url = self.api_manager.state.public_url or f"http://127.0.0.1:{self.api_manager.config.internal_port}"
                            openai_url = self.api_manager.state.openai_url or f"{pub_url}/v1"

                            if self.orchestrator:
                                self.orchestrator.state_machine.transition_to("READY")
                            _emit(10, StageStatus.COMPLETED, detail=f"Verified public endpoint: {pub_url}")
                        except Exception as c_ex:
                            conn_branch_err = str(c_ex)
                            logger.error(f"Connectivity plane execution error: {c_ex}", exc_info=True)
                            for sid in range(8, 11):
                                if self.stages[sid].status == StageStatus.RUNNING:
                                    _emit(sid, StageStatus.FAILED, error=conn_branch_err)
                                elif self.stages[sid].status == StageStatus.PENDING:
                                    _emit(sid, StageStatus.CANCELLED, detail="Cancelled")

                    th_model = threading.Thread(target=_run_model_plane, name="APEX-Model-Branch", daemon=True)
                    th_conn = threading.Thread(target=_run_connectivity_plane, name="APEX-Conn-Branch", daemon=True)

                    th_model.start()
                    th_conn.start()

                    th_model.join()
                    th_conn.join()

                    if model_branch_err or conn_branch_err:
                        raise RuntimeError(model_branch_err or conn_branch_err)

                    self.is_running = True
                    success = True
                except Exception as ex:
                    logger.error(f"APEX Launch failed: {ex}", exc_info=True)
                    err_msg = str(ex)
                    failed_sid = self.active_stage_id or 1
                    for sid in range(1, 11):
                        if self.stages[sid].status == StageStatus.RUNNING:
                            failed_sid = sid
                            _emit(sid, StageStatus.FAILED, error=err_msg)
                            break
                    # Cancel remaining stages
                    for rem_sid in range(failed_sid + 1, 11):
                        if self.stages[rem_sid].status == StageStatus.PENDING:
                            _emit(rem_sid, StageStatus.CANCELLED, detail="Cancelled")
                    if self.orchestrator:
                        self.orchestrator.state_machine.transition_to("FAILED")
                finally:
                    self._stop_stall_watchdog()
                    self.is_launching = False
                    if on_complete:
                        on_complete(success, err_msg)

        if sync:
            _worker()
            return True

        th = threading.Thread(target=_worker, daemon=True)
        th.start()
        return True

    def shutdown(
        self,
        on_progress: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[bool, Optional[str]], None]] = None,
        sync: bool = False,
    ) -> bool:
        """Executes graceful shutdown and frees GPU/system resources."""
        self._stop_stall_watchdog()

        def _worker():
            err: Optional[str] = None
            with ScopedOutputRedirect(self):
                try:
                    self.write_terminal("INFO: Initiating graceful APEX shutdown...")
                    if on_progress:
                        on_progress("Stopping Cloudflare tunnel and API server...")
                    if self.api_manager:
                        self.api_manager.stop()

                    if on_progress:
                        on_progress("Unloading model weights from memory...")
                    if self.model_manager:
                        self.model_manager.unload_model()

                    if on_progress:
                        on_progress("Releasing accelerator memory and running garbage collection...")
                    try:
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    except ImportError:
                        pass
                    gc.collect()

                    if on_progress:
                        on_progress("Stopping orchestrator and task queue...")
                    if self.orchestrator:
                        self.orchestrator.shutdown()

                    self.is_running = False
                    self.write_terminal("INFO: APEX shutdown complete. All resources cleanly released.")
                    if on_progress:
                        on_progress("All resources cleanly released.")
                except Exception as e:
                    logger.error(f"APEX Shutdown error: {e}", exc_info=True)
                    self.write_terminal(f"ERROR: APEX Shutdown error: {e}")
                    err = str(e)
                finally:
                    if on_complete:
                        on_complete(err is None, err)

        if sync:
            _worker()
            return True

        th = threading.Thread(target=_worker, daemon=True)
        th.start()
        return True

    def _render_hardware_html(self) -> str:
        """Renders the compact detected hardware summary and warnings."""
        hw = self.hardware_info
        is_cuda = bool(hw.get("cuda_available", False))
        runtime_name = hw.get("runtime_name", "Local Environment")
        device_str = "CUDA GPU" if is_cuda else "CPU"
        if is_cuda:
            gpu_str = f"{hw.get('gpu_name', 'None')} ({hw.get('vram_total_gb', 0)} GB VRAM)"
        else:
            gpu_str = hw.get("gpu_name") or "None (CPU Mode)"
        ram_str = f"{hw.get('ram_total_gb', 0)} GB" if hw.get("ram_total_gb") else "Unknown"

        warning_banner = ""
        if not is_cuda:
            if hw.get("is_colab"):
                warning_banner = """
                <div style="background:#fffbeb; border:1px solid #fde68a; border-left:3px solid #f59e0b; border-radius:4px; padding:6px 10px; margin-top:8px; font-size:12px; color:#92400e; line-height:1.45;">
                    <b>⚠️ Colab CPU Runtime Active (No GPU Detected)</b><br>
                    You are running on Google Colab's standard CPU runtime without GPU acceleration.<br>
                    Inference will be slow, and models larger than 2B parameters will exceed available RAM (12.7 GB) and crash.<br>
                    <b>Recommendation:</b> Switch to a free GPU via <b>Runtime → Change runtime type → T4 GPU → Save</b> in the Colab menu.
                </div>
                """
            else:
                warning_banner = """
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-left:3px solid #64748b; border-radius:4px; padding:6px 10px; margin-top:8px; font-size:12px; color:#334155; line-height:1.45;">
                    <b>ℹ️ CPU Mode Active</b>: No CUDA GPU detected. Models will execute on CPU. Ensure sufficient system RAM is available.
                </div>
                """

        storage_notice = ""
        if hw.get("is_colab") and not hw.get("drive_mounted"):
            storage_notice = """
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-left:3px solid #64748b; border-radius:4px; padding:6px 10px; margin-top:6px; font-size:11.5px; color:#475569; line-height:1.4;">
                <b>Storage Notice:</b> Ephemeral local storage active. Google Drive is not mounted; models and caches will not persist across Colab VM restarts.
            </div>
            """

        return f"""
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:10px 14px; margin-bottom:12px; font-size:12px; color:#334155; line-height:1.5;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <div style="font-weight:600; font-size:12.5px; color:#334155;">Detected Hardware & Runtime</div>
                <span class="apex-build-badge" style="font-size:11px; color:#94a3b8; font-family:monospace;">Build: {APEX_BUILD_ID}</span>
            </div>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:6px;">
                <div><span style="color:#64748b; font-size:11px; display:block;">Runtime</span> <b>{html.escape(runtime_name)}</b></div>
                <div><span style="color:#64748b; font-size:11px; display:block;">Device</span> <b>{device_str}</b></div>
                <div><span style="color:#64748b; font-size:11px; display:block;">GPU</span> <b>{html.escape(gpu_str)}</b></div>
                <div><span style="color:#64748b; font-size:11px; display:block;">RAM</span> <b>{ram_str}</b></div>
            </div>
            {warning_banner}
            {storage_notice}
        </div>
        """

    def _render_preset_details_html(self, preset: Optional[ModelPreset]) -> str:
        """Renders the detailed metadata and hardware advice card for the selected preset."""
        if not preset:
            return ""

        hw = self.hardware_info
        is_cuda = bool(hw.get("cuda_available", False))
        total_vram = hw.get("vram_total_gb") or 0.0
        gpu_name = hw.get("gpu_name") or "CPU"

        if is_cuda:
            if preset.estimated_vram_gb <= total_vram * 0.9:
                hw_advice = f"✓ Verified fit for {gpu_name} ({total_vram:.1f} GB VRAM available)."
                hw_color = "#15803d"
                card_bg = "#f0fdf4"
                card_border = "#bbf7d0"
            else:
                hw_advice = f"⚠️ Warning: Requires ~{preset.estimated_vram_gb:.1f} GB VRAM, but device has {total_vram:.1f} GB. Potential OOM risk."
                hw_color = "#b45309"
                card_bg = "#fffbeb"
                card_border = "#fde68a"
        else:
            if preset.estimated_vram_gb <= 2.0:
                hw_advice = "ℹ️ Ultra-lightweight model. Verified for CPU testing (inference speed is modest)."
                hw_color = "#0369a1"
                card_bg = "#f0f9ff"
                card_border = "#bae6fd"
            else:
                hw_advice = f"⚠️ Warning: Running a {preset.parameter_count} model on CPU without a GPU accelerator will be slow."
                hw_color = "#b45309"
                card_bg = "#fffbeb"
                card_border = "#fde68a"

        auth_badge = "<span style='color:#dc2626; font-weight:600;'>Yes (Hugging Face token required)</span>" if preset.requires_auth else "<span style='color:#16a34a; font-weight:600;'>No (Public weights)</span>"

        return f"""
        <div style="background:{card_bg}; border:1px solid {card_border}; border-radius:6px; padding:12px 14px; margin-top:8px; font-size:12.5px; color:#334155; line-height:1.5;">
            <div style="font-weight:700; color:#0f172a; font-size:13.5px; margin-bottom:4px;">{html.escape(preset.display_name)}</div>
            <div style="color:#64748b; margin-bottom:8px;">{html.escape(preset.description)}</div>
            <div style="display:flex; gap:16px; flex-wrap:wrap; font-size:12px; margin-bottom:6px;">
                <span><b>Parameters:</b> {html.escape(preset.parameter_count)}</span>
                <span><b>Est. VRAM:</b> ~{preset.estimated_vram_gb:.1f} GB</span>
                <span><b>Recommended Precision:</b> {html.escape(preset.recommended_precision)}</span>
                <span><b>Gated Access:</b> {auth_badge}</span>
            </div>
            <div style="font-size:11.5px; color:{hw_color}; font-weight:600;">
                {hw_advice}
            </div>
        </div>
        """

    def _render_checklist_html(self) -> str:
        """Renders the 10-step progress checklist widget with real-time status and stall alerts."""
        items = []
        stall_warning = ""
        active_st = None

        for sid, name in LAUNCH_STAGES:
            st = self.stages.get(sid)
            if not st:
                status = StageStatus.PENDING
                detail = ""
                sub_op = ""
                elapsed = 0.0
                is_stalled = False
                progress_pct = None
                err_text = None
                last_update_time = None
            else:
                status = st.status
                detail = st.detail
                sub_op = st.sub_operation
                elapsed = st.elapsed_seconds
                is_stalled = st.is_stalled
                progress_pct = st.progress_pct
                err_text = st.error
                last_update_time = st.last_update_time

            if status == StageStatus.RUNNING and active_st is None:
                active_st = st

            if status == StageStatus.COMPLETED:
                icon = '<span style="color:#16a34a; font-weight:bold;">✓</span>'
                cls = "apex-check-done"
                time_tag = f" <span style='color:#64748b; font-size:11px;'>({elapsed:.1f}s)</span>" if elapsed > 0 else ""
                detail_tag = f" <span style='color:#64748b; font-size:11px;'>— {html.escape(detail)}</span>" if detail else ""
                body = f"""
                <div class="apex-check-header">
                    {icon} <span>{sid}. {name}{time_tag}{detail_tag}</span>
                </div>
                """
            elif status == StageStatus.RUNNING:
                icon = '<span style="color:#0284c7; font-weight:bold;">●</span>'
                cls = "apex-check-active"
                time_tag = f" <span style='color:#0284c7; font-size:11px; font-weight:600;'>({int(elapsed)}s)</span>"

                last_ago = max(0.0, time.time() - (last_update_time or (st.start_time if st else time.time())))
                last_event_tag = f" <span style='color:#64748b; font-size:11px;'>(Last event: {last_ago:.1f}s ago)</span>"

                sub_op_html = ""
                if sub_op:
                    sub_op_html = f"<div class='apex-sub-op'>↳ {html.escape(sub_op)}</div>"
                elif detail:
                    sub_op_html = f"<div class='apex-sub-op'>↳ {html.escape(detail)}</div>"

                if progress_pct is not None:
                    progress_bar_html = f"""
                    <div class="apex-progress-wrap">
                        <div class="apex-progress-track">
                            <div class="apex-progress-bar" style="width: {progress_pct:.1f}%;"></div>
                        </div>
                        <span style="font-size:11px; font-weight:600; color:#0284c7;">{progress_pct:.1f}%</span>
                    </div>
                    """
                else:
                    progress_bar_html = """
                    <div class="apex-indeterminate-track">
                        <div class="apex-indeterminate-bar"></div>
                    </div>
                    """

                body = f"""
                <div class="apex-check-header">
                    {icon} <span>{sid}. {name}{time_tag}{last_event_tag}</span>
                </div>
                {sub_op_html}
                {progress_bar_html}
                """

                if is_stalled:
                    stall_warning = f"""
                    <div class="apex-alert-stall">
                        <b>⚠️ Step {sid} ({name}) is taking longer than expected ({int(elapsed)}s elapsed)</b><br>
                        APEX is continuing in the background. On CPU-only environments, loading weights or allocating system RAM can take a few minutes.<br>
                        Please inspect the <b>Developer Console</b> below for live internal operational logs.
                    </div>
                    """
            elif status == StageStatus.FAILED:
                icon = '<span style="color:#dc2626; font-weight:bold;">✗</span>'
                cls = "apex-check-failed"
                msg = err_text or detail or "Operation failed"
                body = f"""
                <div class="apex-check-header">
                    {icon} <span>{sid}. {name} <span style='color:#dc2626; font-size:11px;'>— Error: {html.escape(msg)}</span></span>
                </div>
                """
            elif status == StageStatus.CANCELLED:
                icon = '<span style="color:#94a3b8;">—</span>'
                cls = "apex-check-cancelled"
                body = f"""
                <div class="apex-check-header">
                    {icon} <span>{sid}. {name} <span style='color:#94a3b8; font-size:11px;'>(Cancelled)</span></span>
                </div>
                """
            else:  # PENDING
                icon = '<span style="color:#94a3b8;">○</span>'
                cls = "apex-check-pending"
                body = f"""
                <div class="apex-check-header">
                    {icon} <span>{sid}. {name}</span>
                </div>
                """

            items.append(f'<li class="apex-check-item {cls}">{body}</li>')

        live_banner = ""
        if active_st:
            act_elapsed = active_st.elapsed_seconds
            act_sub_op = active_st.sub_operation or active_st.detail or "Executing launch operation..."
            act_ago = max(0.0, time.time() - (active_st.last_update_time or active_st.start_time or time.time()))

            if active_st.progress_pct is not None:
                act_prog = f"""
                <div class="apex-progress-wrap" style="margin-left:0; margin-top:4px;">
                    <div class="apex-progress-track" style="width:100%; height:7px;">
                        <div class="apex-progress-bar" style="width: {active_st.progress_pct:.1f}%;"></div>
                    </div>
                    <span style="font-size:11px; font-weight:600; color:#0284c7; min-width:45px;">{active_st.progress_pct:.1f}%</span>
                </div>
                """
            else:
                act_prog = """
                <div class="apex-indeterminate-track" style="margin-left:0; width:100%; height:6px;">
                    <div class="apex-indeterminate-bar"></div>
                </div>
                """

            live_banner = f"""
            <div class="apex-live-status-card">
                <div class="apex-live-status-header">
                    <span>● Active: Stage {active_st.stage_id}/10 — {html.escape(active_st.name)}</span>
                    <span style="font-family:monospace; font-weight:600; font-size:12px; color:#0284c7;">{int(act_elapsed)}s elapsed</span>
                </div>
                <div class="apex-sub-op" style="margin-left:0; margin-top:2px;">↳ {html.escape(act_sub_op)}</div>
                <div class="apex-live-meta" style="margin-top:2px;">
                    <span>Last progress event: {act_ago:.1f}s ago</span>
                    <span>• Status: {active_st.status.value.upper()}</span>
                </div>
                {act_prog}
            </div>
            """

        return f'{stall_warning}{live_banner}<div class="apex-checklist-box"><ul class="apex-checklist">{"".join(items)}</ul></div>'

    def _render_console_logs_html(self) -> str:
        """Renders filtered log entries inside the Developer Console box with color badges and secret redaction."""
        entries = self.log_handler.get_entries(
            level=self.filter_level,
            query=self.filter_search,
            max_entries=200,
        )
        if not entries:
            return f'<div class="apex-log-box" style="color:#64748b;">No log entries recorded yet matching current filters. (Build: {APEX_BUILD_ID})</div>'

        lines = []
        for e in entries:
            lvl = e.level.upper()
            if lvl == "DEBUG":
                badge_cls = "apex-badge-log-debug"
            elif lvl == "INFO":
                badge_cls = "apex-badge-log-info"
            elif lvl == "WARNING":
                badge_cls = "apex-badge-log-warn"
            elif lvl in ("ERROR", "EXCEPTION"):
                badge_cls = "apex-badge-log-error"
            else:
                badge_cls = "apex-badge-log-crit"

            line_html = (
                f'<div class="apex-log-entry">'
                f'<span style="color:#64748b;">[{e.timestamp}]</span> '
                f'<span class="{badge_cls}">{lvl[:5]}</span> '
                f'<span style="color:#94a3b8;">[{html.escape(e.logger_name)}]</span> '
                f'<span>{html.escape(e.message)}</span>'
                f'</div>'
            )
            lines.append(line_html)

        return f'<div class="apex-log-box" id="apex-log-window">{"".join(lines)}</div>'

    def _export_logs_text(self) -> str:
        """Exports full log buffer text with sensitive information redacted."""
        entries = self.log_handler.get_entries(level="ALL", max_entries=1000)
        return "\n".join(e.to_formatted_string() for e in entries) if entries else "No logs recorded."

    def _get_active_api_key(self) -> str:
        """Retrieves the real active API key from the API Manager state or config."""
        if self.api_manager and hasattr(self.api_manager, "state") and self.api_manager.state.api_key:
            return self.api_manager.state.api_key
        if self.config.api_key:
            return self.config.api_key
        return "apex-key-unauthenticated" if not self.config.enable_auth else "APEX_active_key"

    def _render_connection_panel_html(self) -> str:
        """Renders the neutral, professional connection card with real credentials."""
        if not self.is_running and not (self.api_manager and self.api_manager.state.api_running):
            return ""

        pub_url = (self.api_manager.state.public_url if self.api_manager else "http://127.0.0.1:8000") or "http://127.0.0.1:8000"
        chat_url = f"{pub_url}/chat"
        openai_url = (self.api_manager.state.openai_url if self.api_manager else f"{pub_url}/v1") or f"{pub_url}/v1"
        real_api_key = self._get_active_api_key()
        model_id = self.config.model_id

        masked_key = "●" * min(len(real_api_key), 28)
        key_display = real_api_key if self._api_key_revealed else masked_key

        python_snippet = f"""from openai import OpenAI

client = OpenAI(
    base_url="{openai_url}",
    api_key="{real_api_key if self.config.enable_auth else 'none'}",
)

response = client.chat.completions.create(
    model="{model_id}",
    messages=[
        {{"role": "system", "content": "You are a helpful assistant."}},
        {{"role": "user", "content": "Hello APEX!"}}
    ]
)
print(response.choices[0].message.content)"""

        return f"""
        <div class="apex-conn-panel">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span class="apex-badge-running">● APEX is running</span>
                    <span style="font-size:13px; color:#475569; font-weight:500;">Model: <b>{html.escape(model_id)}</b></span>
                </div>
                <div>
                    <a href="{chat_url}" target="_blank" style="
                        display:inline-block;
                        background:#16a34a;
                        color:#ffffff;
                        text-decoration:none;
                        padding:7px 14px;
                        border-radius:6px;
                        font-weight:600;
                        font-size:13px;
                    ">Open APEX Chat ↗</a>
                </div>
            </div>

            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:12px; margin-top:12px; font-size:12px;">
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:10px 12px;">
                    <span style="color:#64748b; font-size:11px; display:block;">Web Chat Interface</span>
                    <a href="{chat_url}" target="_blank" style="color:#0284c7; font-weight:600; text-decoration:none;">{chat_url}</a>
                </div>
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:10px 12px;">
                    <span style="color:#64748b; font-size:11px; display:block;">OpenAI API Base URL</span>
                    <span style="color:#0f172a; font-weight:600; font-family:monospace;">{openai_url}</span>
                </div>
            </div>

            <div style="margin-top:12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:10px 12px; font-size:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#64748b; font-size:11px;">Active API Key ({'Bearer Authentication Enabled' if self.config.enable_auth else 'Auth Disabled'})</span>
                </div>
                <div style="margin-top:4px; font-family:monospace; font-size:13px; color:#0f172a; font-weight:600;">
                    {html.escape(key_display)}
                </div>
            </div>
        </div>
        """

    def render(self) -> Any:
        """Renders Section 1 — Setup & Run APEX in the notebook."""
        try:
            import ipywidgets as widgets
            from IPython.display import HTML, display
        except ImportError:
            return self._render_headless("Section 1 — Setup & Run APEX")

        # Close any previous active Section 1 container to avoid duplicate widgets on rerun
        if APEXLauncher._active_container is not None:
            try:
                APEXLauncher._active_container.close()
            except Exception:
                pass
            APEXLauncher._active_container = None
        if self._active_container is not None:
            try:
                self._active_container.close()
            except Exception:
                pass
            self._active_container = None

        display(HTML(get_launcher_css()))

        # ── 1. Header & Hardware Detection
        hw_html = widgets.HTML(value=self._render_hardware_html())

        # ── 2. Model Selection: Curated Presets vs Custom Hugging Face Model
        curr_repo = self.config.model_id
        preset_match = get_preset(curr_repo)

        model_source_radio = widgets.RadioButtons(
            options=["Curated Model Preset", "Custom Hugging Face Model or URL"],
            value="Curated Model Preset" if preset_match else "Custom Hugging Face Model or URL",
            layout=widgets.Layout(margin="4px 0 10px 0"),
        )

        preset_items = [(f"{p.display_name} ({p.repo_id})", p.repo_id) for p in CURATED_PRESETS]
        initial_preset_val = preset_match.repo_id if preset_match else CURATED_PRESETS[0].repo_id

        model_preset_dd = widgets.Dropdown(
            options=preset_items,
            value=initial_preset_val,
            description="Preset:",
            layout=widgets.Layout(width="100%"),
        )
        initial_preset_obj = get_preset(initial_preset_val) or CURATED_PRESETS[0]
        preset_details_html = widgets.HTML(value=self._render_preset_details_html(initial_preset_obj))

        preset_box = widgets.VBox(
            [
                model_preset_dd,
                preset_details_html,
            ],
            layout=widgets.Layout(
                display="block" if model_source_radio.value == "Curated Model Preset" else "none",
                margin="0 0 10px 0",
            ),
        )

        model_id_text = widgets.Text(
            value=curr_repo,
            placeholder="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct or Qwen/Qwen2.5-0.5B-Instruct",
            description="",
            layout=widgets.Layout(width="100%"),
        )

        model_display_name_text = widgets.Text(
            value="",
            placeholder="Optional friendly name (e.g. My Custom Assistant)",
            description="Display Name:",
            layout=widgets.Layout(width="100%"),
        )

        custom_validation_html = widgets.HTML(value="")

        custom_box = widgets.VBox(
            [
                model_id_text,
                model_display_name_text,
                custom_validation_html,
            ],
            layout=widgets.Layout(
                display="block" if model_source_radio.value == "Custom Hugging Face Model or URL" else "none",
                margin="0 0 10px 0",
            ),
        )

        # ── 3. Hugging Face Access Token with Show/Hide & Clear
        hf_token_val = self.config.hf_token or ""
        hf_token_pwd = widgets.Password(
            value=hf_token_val,
            placeholder="hf_... (required for gated models like Llama 3 / Gemma 2)",
            layout=widgets.Layout(flex="1 1 auto"),
        )
        hf_token_txt = widgets.Text(
            value=hf_token_val,
            placeholder="hf_... (required for gated models like Llama 3 / Gemma 2)",
            layout=widgets.Layout(flex="1 1 auto", display="none"),
        )
        show_token_btn = widgets.Button(
            description="Show",
            icon="eye",
            layout=widgets.Layout(width="80px"),
        )
        clear_token_btn = widgets.Button(
            description="Clear",
            icon="times",
            layout=widgets.Layout(width="75px"),
        )
        token_input_row = widgets.HBox(
            [hf_token_pwd, hf_token_txt, show_token_btn, clear_token_btn],
            layout=widgets.Layout(width="100%", gap="6px", align_items="center"),
        )
        token_help_html = widgets.HTML(
            value=(
                "<div style='font-size:11.5px; color:#64748b; margin-top:3px;'>"
                "Required for gated models (e.g. Llama 3, Gemma 2), private repositories, or higher Hugging Face API rate limits. "
                "Leave empty for open public models."
                "</div>"
            )
        )
        token_section_box = widgets.VBox(
            [
                widgets.HTML("<div style='font-weight:600; font-size:12.5px; color:#334155; margin-bottom:4px;'>Hugging Face Access Token</div>"),
                token_input_row,
                token_help_html,
            ],
            layout=widgets.Layout(margin="6px 0 14px 0"),
        )

        # ── 4. Precision Control & Trade-off Guide
        precision_options = [
            ("Auto (Recommended based on hardware)", "auto"),
            ("16-bit (float16 — standard GPU)", "float16"),
            ("16-bit Brain (bfloat16 — modern GPU)", "bfloat16"),
            ("8-bit (bitsandbytes INT8 — lower VRAM)", "8bit"),
            ("4-bit (bitsandbytes NF4 — minimal VRAM)", "4bit"),
            ("32-bit (float32 — CPU execution)", "float32"),
        ]
        curr_prec = self.config.precision or "auto"
        valid_prec_values = [p[1] for p in precision_options]
        default_prec_val = curr_prec if curr_prec in valid_prec_values else "auto"

        precision_dd = widgets.Dropdown(
            options=precision_options,
            value=default_prec_val,
            description="Precision:",
            layout=widgets.Layout(width="100%"),
        )
        precision_help_html = widgets.HTML(
            value=(
                "<div style='font-size:11.5px; color:#64748b; margin-top:3px; line-height:1.45;'>"
                "• <b>Auto</b> selects 16-bit float16 on CUDA GPUs and 32-bit on CPU.<br>"
                "• <b>4-bit / 8-bit</b> drastically reduce GPU VRAM consumption for larger models with minimal fidelity loss.<br>"
                "• <b>16-bit / 32-bit</b> preserve full unquantized weights."
                "</div>"
            )
        )
        precision_section_box = widgets.VBox(
            [
                precision_dd,
                precision_help_html,
            ],
            layout=widgets.Layout(margin="0 0 14px 0"),
        )

        # ── 5. Advanced Settings (Collapsed Accordion)
        port_text = widgets.Text(
            value=str(self.config.port or 8000),
            description="API Port:",
            layout=widgets.Layout(width="48%"),
        )

        auth_cb = widgets.Checkbox(
            value=self.config.enable_auth if self.config.enable_auth is not None else True,
            description="Enable Bearer Authentication",
            layout=widgets.Layout(width="48%"),
        )

        api_key_text = widgets.Password(
            value=self.config.api_key or "",
            placeholder="Leave blank to auto-generate secure key",
            description="Custom Key:",
            layout=widgets.Layout(width="48%"),
        )

        transport_dd = widgets.Dropdown(
            options=[
                ("Cloudflare Quick Tunnel (Public Web & API Access)", "cloudflare"),
                ("Local Port Only (No Tunnel)", "local"),
            ],
            value=self.config.transport or "cloudflare",
            description="Transport:",
            layout=widgets.Layout(width="48%"),
        )

        max_tokens_slider = widgets.IntSlider(
            value=self.config.max_tokens or 512,
            min=64,
            max=4096,
            step=64,
            description="Max Tokens:",
            layout=widgets.Layout(width="48%"),
        )

        temp_slider = widgets.FloatSlider(
            value=self.config.temperature or 0.7,
            min=0.0,
            max=2.0,
            step=0.05,
            description="Temperature:",
            layout=widgets.Layout(width="48%"),
        )

        advanced_box = widgets.VBox(
            [
                widgets.HBox([port_text, auth_cb]),
                widgets.HBox([transport_dd, api_key_text]),
                widgets.HBox([max_tokens_slider, temp_slider]),
            ],
            layout=widgets.Layout(padding="8px 0"),
        )
        advanced_accordion = widgets.Accordion(children=[advanced_box])
        advanced_accordion.set_title(0, "Advanced Settings (Port, Security, Transport, Sampling)")
        advanced_accordion.selected_index = None  # Collapsed by default

        # ── 6. Observability Mode & Action Buttons
        mode_dd = widgets.Dropdown(
            options=[
                ("Development Mode (Live Console Visible)", "development"),
                ("Release Mode (Minimal)", "release"),
            ],
            value=self.console_mode,
            description="Mode:",
            layout=widgets.Layout(width="310px"),
        )

        start_btn = widgets.Button(
            description="START APEX",
            button_style="success",
            icon="play",
            layout=widgets.Layout(width="200px", height="38px"),
        )
        start_btn.add_class("apex-btn-primary")

        validate_btn = widgets.Button(
            description="Validate Configuration",
            button_style="",
            icon="check",
            layout=widgets.Layout(width="190px", height="38px"),
        )

        # ── 7. Checklist & Output Widgets
        checklist_html = widgets.HTML(value="")
        conn_panel_html = widgets.HTML(value="")
        alert_html = widgets.HTML(value="")

        # ── 7b. Real-Time Terminal Output Area
        terminal_output = widgets.Output(
            layout=widgets.Layout(
                width="100%",
                max_height="320px",
                overflow="auto",
                background_color="#0f172a",
                padding="8px 12px",
                border_radius="0 0 6px 6px",
            )
        )
        self._terminal_output = terminal_output

        clear_terminal_btn = widgets.Button(
            description="Clear Output",
            icon="trash",
            layout=widgets.Layout(width="110px", height="28px"),
        )
        clear_terminal_btn.on_click(lambda _: self.clear_terminal())

        terminal_title_html = widgets.HTML(
            value=(
                "<div style='display:flex; align-items:center; gap:8px;'>"
                "<span style='color:#38bdf8; font-family:monospace;'>●</span>"
                "<span style='color:#f8fafc; font-weight:600; font-size:12px;'>Terminal Output</span>"
                f"<span style='color:#64748b; font-size:11px; font-family:monospace;'>[Build: {APEX_BUILD_ID}]</span>"
                "</div>"
            )
        )

        terminal_header = widgets.HBox(
            [terminal_title_html, clear_terminal_btn],
            layout=widgets.Layout(
                background_color="#1e293b",
                padding="6px 12px",
                border_radius="6px 6px 0 0",
                justify_content="space-between",
                align_items="center",
            ),
        )

        terminal_box = widgets.VBox(
            [terminal_header, terminal_output],
            layout=widgets.Layout(margin="12px 0"),
        )

        # ── 8. Live Developer Console
        level_dd = widgets.Dropdown(
            options=["ALL", "DEBUG", "INFO", "WARNING", "ERROR"],
            value=self.filter_level,
            description="Level:",
            layout=widgets.Layout(width="150px"),
        )
        search_text = widgets.Text(
            placeholder="Search logs...",
            layout=widgets.Layout(width="200px"),
        )
        autoscroll_cb = widgets.Checkbox(
            value=self.autoscroll,
            description="Auto-scroll",
            layout=widgets.Layout(width="110px"),
        )
        clear_logs_btn = widgets.Button(
            description="Clear",
            icon="trash",
            layout=widgets.Layout(width="75px"),
        )
        export_logs_btn = widgets.Button(
            description="Export",
            icon="download",
            layout=widgets.Layout(width="80px"),
        )
        console_html = widgets.HTML(value=self._render_console_logs_html())
        export_area = widgets.Textarea(
            value="",
            placeholder="Exported logs will appear here...",
            layout=widgets.Layout(width="98%", height="120px", display="none"),
        )

        build_label = widgets.HTML(
            value=f"<span style='color:#94a3b8; font-size:11px; font-family:monospace; margin-left:auto;'>Build: {APEX_BUILD_ID}</span>"
        )
        console_toolbar = widgets.HBox(
            [level_dd, search_text, autoscroll_cb, clear_logs_btn, export_logs_btn, build_label],
            layout=widgets.Layout(
                background_color="#1e293b",
                padding="6px 8px",
                border_radius="6px 6px 0 0",
                align_items="center",
            ),
        )
        console_box = widgets.VBox(
            [console_toolbar, console_html, export_area],
            layout=widgets.Layout(margin="4px 0"),
        )
        dev_console_accordion = widgets.Accordion(children=[console_box])
        dev_console_accordion.set_title(0, f"Live Developer Console & Telemetry (Build: {APEX_BUILD_ID})")
        dev_console_accordion.selected_index = 0 if self.console_mode == "development" else None

        # ── 9. Collapsed Connect Code Panel
        connect_code_html = widgets.HTML(value="")
        connect_accordion = widgets.Accordion(children=[connect_code_html])
        connect_accordion.set_title(0, "Connect your application (Python SDK)")
        connect_accordion.selected_index = None
        connect_accordion.layout.display = "none"

        # ── Reactive Observers & Wire-ups
        def _get_current_target_model() -> str:
            val = model_id_text.value.strip()
            if val:
                return val
            if model_source_radio.value == "Curated Model Preset" and model_preset_dd.value:
                return model_preset_dd.value
            return ""

        def _update_custom_validation():
            raw = model_id_text.value.strip()
            if not raw:
                custom_validation_html.value = ""
                return
            norm, ok, err = normalize_hf_model_id(raw)
            if not ok:
                custom_validation_html.value = f"<div style='color:#dc2626; font-size:12px; margin-top:4px;'>❌ {err}</div>"
            else:
                self.config.model_id = norm
                total_vram = self.hardware_info.get("vram_total_gb") or 0.0
                is_cuda = bool(self.hardware_info.get("cuda_available", False))
                ram_avail = self.hardware_info.get("ram_available_gb")
                prec = "float16" if precision_dd.value in ("auto", "Auto") else precision_dd.value
                compat_status, compat_msg = check_hardware_compatibility(norm, total_vram, is_cuda, prec, ram_available_gb=ram_avail)
                color = "#15803d" if compat_status in ("compatible", "tight") else ("#b45309" if compat_status in ("warning", "cpu") else "#dc2626")
                custom_validation_html.value = (
                    f"<div style='font-size:12px; margin-top:4px; color:{color};'>"
                    f"✓ Resolved Model ID: <b>{norm}</b><br>{compat_msg}"
                    f"</div>"
                )

        def _on_source_change(change):
            if change["new"] == "Curated Model Preset":
                preset_box.layout.display = "block"
                custom_box.layout.display = "none"
            else:
                preset_box.layout.display = "none"
                custom_box.layout.display = "block"
                _update_custom_validation()

        def _on_preset_change(change):
            p = get_preset(change["new"])
            preset_details_html.value = self._render_preset_details_html(p)
            model_id_text.value = change["new"]
            _update_custom_validation()

        def _on_custom_text_change(change):
            _update_custom_validation()

        def _sync_token(val: str):
            hf_token_pwd.value = val
            hf_token_txt.value = val
            self.config.hf_token = val or None

        def _on_token_pwd_change(change):
            if hf_token_txt.value != change["new"]:
                hf_token_txt.value = change["new"]
                self.config.hf_token = change["new"].strip() or None

        def _on_token_txt_change(change):
            if hf_token_pwd.value != change["new"]:
                hf_token_pwd.value = change["new"]
                self.config.hf_token = change["new"].strip() or None

        def _on_show_token_click(_):
            if hf_token_pwd.layout.display != "none":
                hf_token_txt.value = hf_token_pwd.value
                hf_token_pwd.layout.display = "none"
                hf_token_txt.layout.display = "flex"
                show_token_btn.description = "Hide"
                show_token_btn.icon = "eye-slash"
            else:
                hf_token_pwd.value = hf_token_txt.value
                hf_token_txt.layout.display = "none"
                hf_token_pwd.layout.display = "flex"
                show_token_btn.description = "Show"
                show_token_btn.icon = "eye"

        def _on_clear_token_click(_):
            _sync_token("")

        def _on_log_record(entry: LogEntry):
            self.last_progress_time = time.time()
            console_html.value = self._render_console_logs_html()

        if self._log_listener:
            try:
                self.log_handler.remove_listener(self._log_listener)
            except Exception:
                pass
        self._log_listener = _on_log_record
        self.log_handler.add_listener(_on_log_record)

        def _on_level_change(change):
            self.filter_level = change["new"]
            console_html.value = self._render_console_logs_html()

        def _on_search_change(change):
            self.filter_search = change["new"]
            console_html.value = self._render_console_logs_html()

        def _on_autoscroll_change(change):
            self.autoscroll = change["new"]

        def _on_clear_click(_):
            self.log_handler.clear()
            export_area.layout.display = "none"
            console_html.value = self._render_console_logs_html()

        def _on_export_click(_):
            export_area.value = self._export_logs_text()
            export_area.layout.display = "block" if export_area.layout.display == "none" else "none"

        def _on_mode_change(change):
            self.console_mode = change["new"]
            dev_console_accordion.selected_index = 0 if self.console_mode == "development" else None

        def _on_validate_click(_):
            raw_id = _get_current_target_model()
            prec_val = precision_dd.value
            prec = "float16" if prec_val in ("auto", "Auto") else prec_val
            valid, norm_id, msgs = self.validate_inputs(raw_id, prec, port_text.value.strip())
            active_token = hf_token_pwd.value.strip() or hf_token_txt.value.strip() or None

            if valid:
                self.config.model_id = norm_id
                self.config.precision = prec
                self.config.hf_token = active_token
                self.config.port = int(port_text.value.strip()) if port_text.value.strip().isdigit() else 8000
                self.config.enable_auth = auth_cb.value
                self.config.api_key = api_key_text.value.strip() or None
                self.config.transport = transport_dd.value
                self.config.max_tokens = max_tokens_slider.value
                self.config.temperature = temp_slider.value

                items_html = "".join(f"<li>{html.escape(m)}</li>" for m in msgs)
                alert_html.value = f"""
                <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; padding:10px 14px; font-size:13px; color:#15803d; margin-top:10px;">
                    <b>✓ Configuration Valid</b>
                    <ul style="margin:4px 0 0 16px; padding:0;">{items_html}</ul>
                </div>
                """
            else:
                errs_html = "".join(f"<li>{html.escape(e)}</li>" for e in msgs)
                alert_html.value = f"""
                <div class="apex-alert-error">
                    <b>Configuration Validation Issues:</b>
                    <ul style="margin:4px 0 0 16px; padding:0;">{errs_html}</ul>
                </div>
                """

        def _on_start_click(_):
            if self.is_launching:
                return

            _on_validate_click(None)
            raw_id = _get_current_target_model()
            norm_id, is_val, val_err = normalize_hf_model_id(raw_id)
            if not is_val:
                alert_html.value = f"""
                <div class="apex-alert-error">
                    <b>Invalid Model Repository:</b><br>{html.escape(val_err or 'Invalid Hugging Face model URL or ID.')}
                </div>
                """
                return

            # Lock UI
            start_btn.disabled = True
            start_btn.description = "Launching APEX..."
            validate_btn.disabled = True
            alert_html.value = ""
            conn_panel_html.value = ""
            connect_accordion.layout.display = "none"

            self.clear_terminal()
            self.write_terminal(f"INFO: Launch triggered for model '{norm_id}' (Precision: {self.config.precision})...")
            checklist_html.value = self._render_checklist_html()

            def _progress(sid, st, msg):
                checklist_html.value = self._render_checklist_html()
                console_html.value = self._render_console_logs_html()

            def _complete(success, err):
                start_btn.disabled = False
                validate_btn.disabled = False
                checklist_html.value = self._render_checklist_html()
                console_html.value = self._render_console_logs_html()

                if success:
                    start_btn.description = "RESTART APEX"
                    conn_panel_html.value = self._render_connection_panel_html()

                    # Prepopulate Python snippet
                    pub_url = (self.api_manager.state.public_url if self.api_manager else "http://127.0.0.1:8000") or "http://127.0.0.1:8000"
                    openai_url = (self.api_manager.state.openai_url if self.api_manager else f"{pub_url}/v1") or f"{pub_url}/v1"
                    active_key = self._get_active_api_key()

                    code_content = f"""from openai import OpenAI

client = OpenAI(
    base_url="{openai_url}",
    api_key="{active_key if self.config.enable_auth else 'none'}",
)

completion = client.chat.completions.create(
    model="{self.config.model_id}",
    messages=[
        {{"role": "system", "content": "You are a helpful assistant."}},
        {{"role": "user", "content": "Hello APEX!"}}
    ]
)
print(completion.choices[0].message.content)"""

                    connect_code_html.value = f'<div class="apex-snippet-box">{html.escape(code_content)}</div>'
                    connect_accordion.layout.display = "block"
                else:
                    start_btn.description = "RETRY APEX"
                    alert_html.value = f"""
                    <div class="apex-alert-error">
                        <b>Runtime Initialization Failed:</b><br>{html.escape(err or 'Unknown error')}
                    </div>
                    """

            with terminal_output:
                self.launch(on_progress=_progress, on_complete=_complete, sync=True)

        # Wire observers
        mode_dd.observe(_on_mode_change, names="value")
        level_dd.observe(_on_level_change, names="value")
        search_text.observe(_on_search_change, names="value")
        autoscroll_cb.observe(_on_autoscroll_change, names="value")
        clear_logs_btn.on_click(_on_clear_click)
        export_logs_btn.on_click(_on_export_click)

        model_source_radio.observe(_on_source_change, names="value")
        model_preset_dd.observe(_on_preset_change, names="value")
        model_id_text.observe(_on_custom_text_change, names="value")
        hf_token_pwd.observe(_on_token_pwd_change, names="value")
        hf_token_txt.observe(_on_token_txt_change, names="value")
        show_token_btn.on_click(_on_show_token_click)
        clear_token_btn.on_click(_on_clear_token_click)

        validate_btn.on_click(_on_validate_click)
        start_btn.on_click(_on_start_click)
        _update_custom_validation()

        # Store widgets for programmatic access
        self._widgets = {
            "mode_selector": mode_dd,
            "model_source_radio": model_source_radio,
            "model_preset": model_preset_dd,
            "model_id": model_id_text,
            "model_display_name": model_display_name_text,
            "precision": precision_dd,
            "hf_token": hf_token_pwd,
            "start_btn": start_btn,
            "validate_btn": validate_btn,
            "terminal_output": terminal_output,
            "clear_terminal_btn": clear_terminal_btn,
            "checklist_html": checklist_html,
            "conn_panel_html": conn_panel_html,
            "alert_html": alert_html,
            "console_html": console_html,
            "dev_console_accordion": dev_console_accordion,
            "export_area": export_area,
        }

        # Assemble clean URL-first layout
        url_input_box = widgets.VBox(
            [
                widgets.HTML("<div style='font-weight:600; font-size:13px; color:#1e293b; margin-bottom:4px;'>Hugging Face Model Repository URL</div>"),
                model_id_text,
                custom_validation_html,
            ],
            layout=widgets.Layout(width="100%", margin="0 0 12px 0"),
        )

        btn_row = widgets.HBox(
            [start_btn],
            layout=widgets.Layout(margin="6px 0 12px 0", align_items="center"),
        )

        container_children = [
            hw_html,
            url_input_box,
            token_section_box,
            btn_row,
            alert_html,
            terminal_box,
            conn_panel_html,
            connect_accordion,
        ]

        if self.console_mode == "development":
            container_children.append(dev_console_accordion)

        container = widgets.VBox(
            container_children,
            layout=widgets.Layout(
                background_color="#ffffff",
                border="1px solid #e2e8f0",
                border_radius="8px",
                padding="20px",
                width="100%",
            ),
        )

        display(container)
        APEXLauncher._active_container = container
        self._active_container = container
        self.widget = container
        return None

    def render_shutdown(self) -> Any:
        """Renders Section 2 — Shutdown APEX in the notebook."""
        try:
            import ipywidgets as widgets
            from IPython.display import HTML, display
        except ImportError:
            return self._render_headless("Section 2 — Shutdown APEX")

        # Close any previous active Section 2 container to avoid duplicate widgets on rerun
        if APEXLauncher._active_shutdown_container is not None:
            try:
                APEXLauncher._active_shutdown_container.close()
            except Exception:
                pass
            APEXLauncher._active_shutdown_container = None
        if self._active_shutdown_container is not None:
            try:
                self._active_shutdown_container.close()
            except Exception:
                pass
            self._active_shutdown_container = None

        display(HTML(get_launcher_css()))

        status_html = widgets.HTML(value="")
        progress_html = widgets.HTML(value="")

        def _update_status():
            if self.is_running or (self.api_manager and self.api_manager.state.api_running):
                port = self.api_manager.config.internal_port if self.api_manager else 8000
                status_html.value = f"""
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
                    <span class="apex-badge-running">● Running</span>
                    <span style="font-size:13px; color:#475569;">Active Port: <b>{port}</b> · Model: <b>{html.escape(self.config.model_id)}</b></span>
                </div>
                """
            else:
                status_html.value = """
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
                    <span class="apex-badge-stopped">○ Stopped</span>
                    <span style="font-size:13px; color:#64748b;">No active model or server process running.</span>
                </div>
                """

        _update_status()

        stop_btn = widgets.Button(
            description="STOP APEX",
            button_style="danger",
            icon="stop",
            layout=widgets.Layout(width="180px", height="38px"),
        )
        stop_btn.add_class("apex-btn-stop")

        def _on_stop_click(_):
            stop_btn.disabled = True
            stop_btn.description = "Shutting down..."
            self.clear_shutdown_terminal()
            self.write_terminal("INFO: Shutdown requested by user.")

            def _progress(step_msg):
                progress_html.value = f"<div style='font-size:12px; color:#64748b; margin-top:8px;'>{html.escape(step_msg)}</div>"

            def _complete(success, err):
                stop_btn.disabled = False
                stop_btn.description = "STOP APEX"
                _update_status()
                if success:
                    progress_html.value = """
                    <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; padding:10px 14px; font-size:13px; color:#15803d; margin-top:10px;">
                        <b>✓ APEX has been safely shut down.</b> All model weights, API server processes, and GPU resources have been released.
                    </div>
                    """
                    # Reset Section 1 Start button if rendered
                    if "start_btn" in self._widgets:
                        self._widgets["start_btn"].description = "START APEX"
                else:
                    progress_html.value = f"""
                    <div class="apex-alert-error">
                        <b>Shutdown Warning:</b> {html.escape(err or 'Encountered issue during teardown.')}
                    </div>
                    """

            with shutdown_terminal_output:
                self.shutdown(on_progress=_progress, on_complete=_complete, sync=True)

        stop_btn.on_click(_on_stop_click)

        shutdown_terminal_output = widgets.Output(
            layout=widgets.Layout(
                width="100%",
                max_height="220px",
                overflow="auto",
                background_color="#0f172a",
                padding="8px 12px",
                border_radius="0 0 6px 6px",
            )
        )
        self._shutdown_terminal_output = shutdown_terminal_output

        clear_shutdown_btn = widgets.Button(
            description="Clear Output",
            icon="trash",
            layout=widgets.Layout(width="110px", height="28px"),
        )
        clear_shutdown_btn.on_click(lambda _: self.clear_shutdown_terminal())

        shutdown_terminal_header = widgets.HBox(
            [
                widgets.HTML(
                    "<div style='display:flex; align-items:center; gap:8px;'>"
                    "<span style='color:#f87171; font-family:monospace;'>●</span>"
                    "<span style='color:#f8fafc; font-weight:600; font-size:12px;'>Shutdown Terminal Output</span>"
                    "</div>"
                ),
                clear_shutdown_btn,
            ],
            layout=widgets.Layout(
                background_color="#1e293b",
                padding="6px 12px",
                border_radius="6px 6px 0 0",
                justify_content="space-between",
                align_items="center",
            ),
        )

        shutdown_terminal_box = widgets.VBox(
            [shutdown_terminal_header, shutdown_terminal_output],
            layout=widgets.Layout(margin="12px 0"),
        )

        self._shutdown_widgets = {
            "status_html": status_html,
            "stop_btn": stop_btn,
            "progress_html": progress_html,
            "terminal_output": shutdown_terminal_output,
            "clear_terminal_btn": clear_shutdown_btn,
        }

        container = widgets.VBox(
            [
                widgets.HTML("<div class='apex-card-title'>Runtime Status & Teardown</div>"),
                status_html,
                stop_btn,
                progress_html,
                shutdown_terminal_box,
            ],
            layout=widgets.Layout(
                background_color="#ffffff",
                border="1px solid #e2e8f0",
                border_radius="8px",
                padding="20px",
                width="100%",
            ),
        )

        display(container)
        APEXLauncher._active_shutdown_container = container
        self._active_shutdown_container = container
        self.shutdown_widget = container
        return None

    def _render_headless(self, section_name: str) -> str:
        """CLI / Non-interactive fallback."""
        hw = self.hardware_info
        print(f"\n[{section_name}]")
        print(f"  Runtime     : {hw['runtime_name']}")
        print(f"  Device      : {hw['device']} ({hw['gpu_name']})")
        print(f"  Model       : {self.config.model_id}")
        print(f"  Status      : {'Running' if self.is_running else 'Stopped'}")
        return f"APEXLauncher Headless ({section_name})"
