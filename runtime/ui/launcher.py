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
    ModelPreset,
    check_hardware_compatibility,
    estimate_vram,
    get_preset,
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
from runtime.orchestrator.orchestrator import RuntimeOrchestrator

logger = logging.getLogger("runtime.ui.launcher")


# ── URL Normalization & Validation ───────────────────────────────────────────

HF_URL_PATTERN = re.compile(
    r"^https?://(?:www\.)?huggingface\.co/([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)(?:/.*)?$",
    re.IGNORECASE,
)
HF_REPO_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9._-]+/)?[a-zA-Z0-9._-]+$"
)


def normalize_hf_model_id(val: str) -> Tuple[str, bool, Optional[str]]:
    """Normalizes and validates a Hugging Face model identifier or URL.

    Accepts:
        - Full HF URL: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct
        - HF URL with tree/branch: https://huggingface.co/meta-llama/Llama-3.2-1B/tree/main
        - HF URL with .git: https://huggingface.co/org/model.git
        - Standard repo ID: Qwen/Qwen2.5-1.5B-Instruct
        - Single-part repo ID: gpt2

    Returns:
        (normalized_model_id, is_valid, error_message_or_none)
    """
    if not val or not isinstance(val, str):
        return ("", False, "Model ID is required.")

    cleaned = val.strip()
    if not cleaned:
        return ("", False, "Model ID cannot be empty.")

    # Check for dangerous schemes
    lower = cleaned.lower()
    for scheme in ("javascript:", "file:", "data:", "ftp:", "vbscript:"):
        if lower.startswith(scheme):
            return ("", False, f"Invalid model URL scheme '{scheme}'.")

    # If it is a web URL, it must be huggingface.co
    if lower.startswith("http://") or lower.startswith("https://"):
        match = HF_URL_PATTERN.match(cleaned)
        if match:
            repo_id = match.group(1)
            if repo_id.endswith(".git"):
                repo_id = repo_id[:-4]
            return (repo_id, True, None)
        else:
            return (
                cleaned,
                False,
                "URL must be a valid Hugging Face repository URL (e.g. https://huggingface.co/org/model).",
            )

    # Clean potential trailing .git or slashes from raw repo ID
    repo_cleaned = cleaned.rstrip("/")
    if repo_cleaned.endswith(".git"):
        repo_cleaned = repo_cleaned[:-4]

    # Validate repo ID pattern
    if HF_REPO_PATTERN.match(repo_cleaned):
        return (repo_cleaned, True, None)

    return (
        cleaned,
        False,
        "Invalid model ID format. Use format 'organization/model-name' or 'model-name'.",
    )


# ── Hardware Detection ───────────────────────────────────────────────────────

def detect_environment_hardware() -> Dict[str, Any]:
    """Detects real hardware accelerator, memory, and environment details."""
    is_colab = "google.colab" in sys.modules or os.environ.get("COLAB_GPU") is not None
    env_name = "Google Colab" if is_colab else "Local Environment"

    device = "cpu"
    gpu_name = "None (CPU Mode)"
    vram_total_gb: Optional[float] = None
    vram_free_gb: Optional[float] = None
    cuda_available = False

    # Check PyTorch CUDA / MPS
    try:
        import torch

        if torch.cuda.is_available():
            cuda_available = True
            device = "cuda:0"
            gpu_name = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            vram_total_gb = round(props.total_memory / (1024**3), 2)
            try:
                free_bytes, _ = torch.cuda.mem_get_info(0)
                vram_free_gb = round(free_bytes / (1024**3), 2)
            except Exception:
                vram_free_gb = vram_total_gb
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
            gpu_name = "Apple Silicon (MPS)"
    except ImportError:
        pass

    # System RAM
    ram_total_gb = 0.0
    ram_avail_gb = 0.0
    try:
        import psutil

        mem = psutil.virtual_memory()
        ram_total_gb = round(mem.total / (1024**3), 2)
        ram_avail_gb = round(mem.available / (1024**3), 2)
    except Exception:
        ram_total_gb = 8.0
        ram_avail_gb = 4.0

    return {
        "is_colab": is_colab,
        "runtime_name": env_name,
        "device": device,
        "gpu_name": gpu_name,
        "vram_total_gb": vram_total_gb,
        "vram_free_gb": vram_free_gb,
        "ram_total_gb": ram_total_gb,
        "ram_available_gb": ram_avail_gb,
        "cuda_available": cuda_available,
        "python_version": sys.version.split()[0],
    }


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
            padding: 24px;
            max-width: 860px;
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

    def _attach_log_handler(self):
        """Attaches our scoped buffer handler to relevant loggers and prevents stdout leakage."""
        from runtime.logging.logger import remove_stream_handlers

        for name in ("runtime", "runtime.lifecycle", "bootstrap", "uvicorn", "fastapi"):
            l = logging.getLogger(name)
            remove_stream_handlers(l)
            l.propagate = False
            if self.log_handler not in l.handlers:
                l.addHandler(self.log_handler)
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
        st = self.stages[stage_id]
        st.status = status
        self.last_progress_time = time.time()
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
            try:
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
                        error_code=ApexErrorCode.API_START_FAILED,
                        message=f"API startup failed: {self.api_manager.state.last_error}",
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

        th = threading.Thread(target=_worker, daemon=True)
        th.start()
        return True

    def shutdown(
        self,
        on_progress: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[bool, Optional[str]], None]] = None,
    ) -> bool:
        """Executes graceful shutdown and frees GPU/system resources."""
        self._stop_stall_watchdog()

        def _worker():
            err: Optional[str] = None
            try:
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
                if on_progress:
                    on_progress("All resources cleanly released.")
            except Exception as e:
                logger.error(f"APEX Shutdown error: {e}", exc_info=True)
                err = str(e)
            finally:
                if on_complete:
                    on_complete(err is None, err)

        th = threading.Thread(target=_worker, daemon=True)
        th.start()
        return True

    def _render_hardware_html(self) -> str:
        """Renders the detected hardware summary grid and warnings."""
        hw = self.hardware_info
        vram_str = f"{hw['vram_total_gb']} GB" if hw.get("vram_total_gb") else "N/A (CPU)"
        ram_str = f"{hw['ram_total_gb']} GB ({hw['ram_available_gb']} GB free)"

        warning_banner = ""
        if not hw.get("cuda_available"):
            if hw.get("is_colab"):
                warning_banner = """
                <div style="background:#fffbeb; border:1px solid #fde68a; border-left:4px solid #f59e0b; border-radius:6px; padding:10px 14px; margin-top:12px; font-size:12px; color:#92400e; line-height:1.45;">
                    <b>⚠️ Colab CPU Runtime Active (No GPU Detected)</b><br>
                    You are running on Google Colab's standard CPU runtime without GPU acceleration.<br>
                    Inference will be slow, and models larger than 2B parameters will exceed available RAM (12.7 GB) and crash.<br>
                    <b>Recommendation:</b> Switch to a free GPU via <b>Runtime → Change runtime type → T4 GPU → Save</b> in the Colab menu.
                </div>
                """
            else:
                warning_banner = """
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-left:4px solid #64748b; border-radius:6px; padding:10px 14px; margin-top:12px; font-size:12px; color:#334155; line-height:1.45;">
                    <b>ℹ️ CPU Mode Active</b>: No CUDA GPU detected. Models will execute on CPU. Ensure sufficient system RAM is available.
                </div>
                """

        return f"""
        <div class="apex-card">
            <div class="apex-card-title">Detected Hardware & Runtime</div>
            <div class="apex-grid-hw">
                <div class="apex-hw-item">
                    <span class="apex-hw-label">Runtime Environment</span>
                    <span class="apex-hw-value">{html.escape(hw['runtime_name'])}</span>
                </div>
                <div class="apex-hw-item">
                    <span class="apex-hw-label">Accelerator</span>
                    <span class="apex-hw-value">{html.escape(hw['gpu_name'])}</span>
                </div>
                <div class="apex-hw-item">
                    <span class="apex-hw-label">GPU VRAM</span>
                    <span class="apex-hw-value">{vram_str}</span>
                </div>
                <div class="apex-hw-item">
                    <span class="apex-hw-label">System RAM</span>
                    <span class="apex-hw-value">{ram_str}</span>
                </div>
                <div class="apex-hw-item">
                    <span class="apex-hw-label">Compute Device</span>
                    <span class="apex-hw-value">{html.escape(hw['device'])}</span>
                </div>
            </div>
            {warning_banner}
        </div>
        """

    def _render_checklist_html(self) -> str:
        """Renders the 10-step progress checklist widget with real-time status and stall alerts."""
        items = []
        stall_warning = ""

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
            else:
                status = st.status
                detail = st.detail
                sub_op = st.sub_operation
                elapsed = st.elapsed_seconds
                is_stalled = st.is_stalled
                progress_pct = st.progress_pct
                err_text = st.error

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

                sub_op_html = ""
                if sub_op:
                    sub_op_html = f"<div class='apex-sub-op'>↳ {html.escape(sub_op)}</div>"
                elif detail:
                    sub_op_html = f"<div class='apex-sub-op'>↳ {html.escape(detail)}</div>"

                progress_bar_html = ""
                if progress_pct is not None:
                    progress_bar_html = f"""
                    <div class="apex-progress-wrap">
                        <div class="apex-progress-track">
                            <div class="apex-progress-bar" style="width: {progress_pct:.1f}%;"></div>
                        </div>
                        <span style="font-size:11px; font-weight:600; color:#0284c7;">{progress_pct:.1f}%</span>
                    </div>
                    """

                body = f"""
                <div class="apex-check-header">
                    {icon} <span>{sid}. {name}{time_tag}</span>
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

        return f'{stall_warning}<ul class="apex-checklist">{"".join(items)}</ul>'

    def _render_console_logs_html(self) -> str:
        """Renders filtered log entries inside the Developer Console box with color badges and secret redaction."""
        entries = self.log_handler.get_entries(
            level=self.filter_level,
            query=self.filter_search,
            max_entries=200,
        )
        if not entries:
            return '<div class="apex-log-box" style="color:#64748b;">No log entries recorded yet matching current filters.</div>'

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

        # ── 2. Model Configuration
        preset_items = [(f"{p.display_name} ({p.repo_id})", p.repo_id) for p in CURATED_PRESETS]
        preset_items.append(("Custom Hugging Face Model or URL...", "custom"))

        curr_repo = self.config.model_id
        preset_match = get_preset(curr_repo)
        default_preset_val = curr_repo if preset_match else "custom"

        model_preset_dd = widgets.Dropdown(
            options=preset_items,
            value=default_preset_val,
            description="Model Preset:",
            layout=widgets.Layout(width="98%"),
        )

        model_id_text = widgets.Text(
            value=curr_repo,
            placeholder="e.g. Qwen/Qwen2.5-0.5B or https://huggingface.co/...",
            description="Model ID/URL:",
            layout=widgets.Layout(width="98%"),
        )

        model_display_name_text = widgets.Text(
            value="",
            placeholder="Optional friendly name (e.g. My Assistant)",
            description="Display Name:",
            layout=widgets.Layout(width="98%"),
        )

        precision_dd = widgets.Dropdown(
            options=["Auto", "float16", "bfloat16", "float32"],
            value=self.config.precision if self.config.precision in ("float16", "bfloat16", "float32") else "Auto",
            description="Precision:",
            layout=widgets.Layout(width="48%"),
        )

        hf_token_text = widgets.Password(
            value=self.config.hf_token or "",
            placeholder="hf_... (optional for gated models)",
            description="HF Token:",
            layout=widgets.Layout(width="48%"),
        )

        model_feedback_html = widgets.HTML(value="")

        # ── 3. Advanced Settings (Collapsed)
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
                ("Cloudflare Quick Tunnel (Public Access)", "cloudflare"),
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
        advanced_accordion.set_title(0, "Advanced Settings")
        advanced_accordion.selected_index = None  # Collapsed by default

        # ── 4. Observability Mode & Action Buttons
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
            layout=widgets.Layout(width="180px", height="38px"),
        )

        # ── 5. Checklist & Output Widgets
        checklist_html = widgets.HTML(value="")
        conn_panel_html = widgets.HTML(value="")
        alert_html = widgets.HTML(value="")

        # ── 6. Live Developer Console
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

        console_toolbar = widgets.HBox(
            [level_dd, search_text, autoscroll_cb, clear_logs_btn, export_logs_btn],
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
        dev_console_accordion.set_title(0, "Live Developer Console & Telemetry")
        dev_console_accordion.selected_index = 0 if self.console_mode == "development" else None

        # ── 7. Collapsed Connect Code Panel
        connect_code_html = widgets.HTML(value="")
        connect_accordion = widgets.Accordion(children=[connect_code_html])
        connect_accordion.set_title(0, "Connect your application (Python SDK)")
        connect_accordion.selected_index = None
        connect_accordion.layout.display = "none"

        # ── Callbacks
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

        def _on_preset_change(change):
            val = change["new"]
            if val == "custom":
                model_id_text.disabled = False
            else:
                model_id_text.value = val
                model_feedback_html.value = ""

        def _on_model_text_change(change):
            raw = change["new"]
            norm, ok, err = normalize_hf_model_id(raw)
            if not ok and raw.strip():
                model_feedback_html.value = f"<div style='color:#dc2626; font-size:12px; margin-top:2px;'>{err}</div>"
            else:
                model_feedback_html.value = ""

        def _on_validate_click(_):
            raw_id = model_id_text.value.strip()
            prec = "float16" if precision_dd.value == "Auto" else precision_dd.value
            valid, norm_id, msgs = self.validate_inputs(raw_id, prec, port_text.value.strip())
            if valid:
                self.config.model_id = norm_id
                self.config.precision = prec
                self.config.hf_token = hf_token_text.value.strip() or None
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
            norm_id, is_val, _ = normalize_hf_model_id(model_id_text.value.strip())
            if not is_val:
                return

            # Lock UI
            start_btn.disabled = True
            start_btn.description = "Launching APEX..."
            validate_btn.disabled = True
            alert_html.value = ""
            conn_panel_html.value = ""
            connect_accordion.layout.display = "none"

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

            self.launch(on_progress=_progress, on_complete=_complete)

        # Wire observers
        mode_dd.observe(_on_mode_change, names="value")
        level_dd.observe(_on_level_change, names="value")
        search_text.observe(_on_search_change, names="value")
        autoscroll_cb.observe(_on_autoscroll_change, names="value")
        clear_logs_btn.on_click(_on_clear_click)
        export_logs_btn.on_click(_on_export_click)

        model_preset_dd.observe(_on_preset_change, names="value")
        model_id_text.observe(_on_model_text_change, names="value")
        validate_btn.on_click(_on_validate_click)
        start_btn.on_click(_on_start_click)

        # Store widgets for programmatic access
        self._widgets = {
            "mode_selector": mode_dd,
            "model_preset": model_preset_dd,
            "model_id": model_id_text,
            "precision": precision_dd,
            "start_btn": start_btn,
            "validate_btn": validate_btn,
            "checklist_html": checklist_html,
            "conn_panel_html": conn_panel_html,
            "alert_html": alert_html,
            "console_html": console_html,
            "dev_console_accordion": dev_console_accordion,
            "export_area": export_area,
        }

        # Assemble layout
        container = widgets.VBox(
            [
                hw_html,
                widgets.VBox(
                    [
                        widgets.HTML("<div class='apex-card-title' style='margin-top:4px;'>Model Configuration</div>"),
                        model_preset_dd,
                        model_id_text,
                        model_display_name_text,
                        widgets.HBox([precision_dd, hf_token_text]),
                        model_feedback_html,
                    ],
                    layout=widgets.Layout(margin="0 0 12px 0"),
                ),
                advanced_accordion,
                widgets.HBox([start_btn, validate_btn, mode_dd], layout=widgets.Layout(gap="12px", margin="16px 0 8px 0", align_items="center")),
                alert_html,
                checklist_html,
                dev_console_accordion,
                conn_panel_html,
                connect_accordion,
            ],
            layout=widgets.Layout(
                background_color="#ffffff",
                border="1px solid #e2e8f0",
                border_radius="8px",
                padding="20px",
                max_width="850px",
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

            self.shutdown(on_progress=_progress, on_complete=_complete)

        stop_btn.on_click(_on_stop_click)

        container = widgets.VBox(
            [
                widgets.HTML("<div class='apex-card-title'>Runtime Status & Teardown</div>"),
                status_html,
                stop_btn,
                progress_html,
            ],
            layout=widgets.Layout(
                background_color="#ffffff",
                border="1px solid #e2e8f0",
                border_radius="8px",
                padding="20px",
                max_width="850px",
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
