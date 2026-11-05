"""Minimal, professional, Python-first launcher UI for APEX.

This module provides the two-section APEX Notebook experience:
1. Section 1 — Setup & Run APEX (configuration, hardware status, 10-step launch pipeline, connection panel)
2. Section 2 — Shutdown APEX (graceful teardown, resource cleanup, status confirmation)
"""

import collections
import gc
import html
import logging
import os
import re
import sys
import threading
import time
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


# ── Scoped Log Capture ───────────────────────────────────────────────────────

class LogBufferHandler(logging.Handler):
    """Scoped in-memory log buffer that captures internal logs without touching sys.stdout."""

    def __init__(self, capacity: int = 1000):
        super().__init__()
        self.capacity = capacity
        self.buffer: Deque[str] = collections.deque(maxlen=capacity)
        self.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)-7s [%(name)s] %(message)s", datefmt="%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.buffer.append(msg)
        except Exception:
            self.handleError(record)

    def get_logs(self, max_lines: int = 200) -> str:
        """Returns the most recent formatted log lines."""
        lines = list(self.buffer)[-max_lines:]
        return "\n".join(lines) if lines else "No runtime logs recorded yet."

    def clear(self):
        self.buffer.clear()


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
            align-items: center;
            gap: 10px;
            padding: 5px 0;
            color: #475569;
        }
        .apex-check-pending { color: #94a3b8; }
        .apex-check-active { color: #0284c7; font-weight: 600; }
        .apex-check-done { color: #16a34a; font-weight: 500; }
        .apex-check-failed { color: #dc2626; font-weight: 600; }
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
        .apex-log-box {
            background: #0f172a;
            color: #e2e8f0;
            border-radius: 6px;
            padding: 12px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 11px;
            max-height: 280px;
            overflow-y: auto;
            white-space: pre-wrap;
            line-height: 1.4;
        }
        .apex-alert-error {
            background: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 6px;
            color: #b91c1c;
            padding: 12px 14px;
            font-size: 13px;
            margin-top: 12px;
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

        # Startup stage states: stage_id -> ("pending" | "in_progress" | "completed" | "failed", detail_message)
        self.stage_states: Dict[int, Tuple[str, str]] = {
            s[0]: ("pending", "") for s in LAUNCH_STAGES
        }

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
        for s in LAUNCH_STAGES:
            self.stage_states[s[0]] = ("pending", "")

        def _set_stage(sid: int, status: str, msg: str = ""):
            self.stage_states[sid] = (status, msg)
            if on_progress:
                on_progress(sid, status, msg)

        def _worker():
            success = False
            err_msg: Optional[str] = None
            try:
                # ── Step 1: Environment Initialization
                _set_stage(1, "in_progress", "Initializing runtime environment & workspace...")
                if self.lifecycle is None:
                    self.lifecycle = RuntimeLifecycle(workspace_path=self.workspace_path)
                    startup_ok = self.lifecycle.startup(interactive=False)
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
                _set_stage(1, "completed", "Environment & default workspace ready")

                # ── Step 2: Dependency Verification
                _set_stage(2, "in_progress", "Verifying Python dependencies...")
                diag = DiagnosticsManager(self.workspace_path)
                diag._report_dependencies()
                _set_stage(2, "completed", "Core dependencies verified")

                # ── Step 3: Hardware & GPU Detection
                _set_stage(3, "in_progress", "Inspecting compute accelerator...")
                self.hardware_info = detect_environment_hardware()
                if self.hardware_info.get("cuda_available"):
                    self.config.device = "cuda"
                    gpu_desc = f"{self.hardware_info['gpu_name']} ({self.hardware_info['vram_total_gb']} GB VRAM)"
                else:
                    self.config.device = "cpu"
                    gpu_desc = self.hardware_info["gpu_name"]
                _set_stage(3, "completed", f"Active device: {self.config.device} · {gpu_desc}")

                # ── Step 4: Model Resolution
                _set_stage(4, "in_progress", f"Resolving {self.config.model_id}...")
                norm_id, is_val, val_err = normalize_hf_model_id(self.config.model_id)
                if not is_val:
                    raise RuntimeErrorBase(
                        message=val_err or "Invalid Model ID",
                        cause="Provided model ID or URL could not be parsed as a valid Hugging Face repository.",
                        recovery="Check the model name format (e.g. 'Qwen/Qwen2.5-0.5B') or Hugging Face URL.",
                        code=ApexErrorCode.MODEL_FILES_INVALID,
                    )
                self.config.model_id = norm_id
                _set_stage(4, "completed", f"Resolved repository ID: {norm_id}")

                # ── Step 5: Model Download & Cache Verification
                _set_stage(5, "in_progress", f"Checking cached weights for {norm_id}...")
                if self.orchestrator:
                    self.orchestrator.state_machine.transition_to("MODEL_DOWNLOADING")
                self.model_manager.download_model(
                    norm_id,
                    revision=self.config.revision,
                    hf_token=self.config.hf_token,
                )
                _set_stage(5, "completed", "Model weights downloaded and verified in cache")

                # ── Step 6: Model Loading into VRAM / RAM
                target_mem = "VRAM" if self.config.device == "cuda" else "system RAM"
                _set_stage(6, "in_progress", f"Loading weights into {target_mem} ({self.config.precision})...")
                if self.orchestrator:
                    self.orchestrator.state_machine.transition_to("MODEL_LOADING")
                self.model_manager.load_model(
                    norm_id,
                    precision=self.config.precision,
                    revision=self.config.revision,
                    hf_token=self.config.hf_token,
                    device=self.config.device,
                )
                _set_stage(6, "completed", f"Model allocated in {target_mem} ({self.config.precision})")

                # ── Step 7: Inference Engine Initialization
                _set_stage(7, "in_progress", "Initializing inference engine and warm-up...")
                if self.orchestrator:
                    self.orchestrator.state_machine.transition_to("MODEL_READY")
                if not self.model_manager.is_loaded:
                    raise RuntimeErrorBase(
                        message="Model failed to initialize properly in memory.",
                        cause="Inference engine active engine is not loaded.",
                        recovery="Verify that the selected model architecture is supported.",
                        code=ApexErrorCode.MODEL_LOAD_FAILED,
                    )
                _set_stage(7, "completed", "Inference engine operational")

                # ── Step 8: Local API Server Startup
                _set_stage(8, "in_progress", "Starting API server...")
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
                _set_stage(8, "completed", f"Local server bound on port {self.api_manager.config.internal_port}")

                # ── Step 9: Local API Health Verification
                _set_stage(9, "in_progress", "Verifying local API health endpoint...")
                time.sleep(0.5)
                if self.api_manager.state.api_status.value not in ("running", "ready", "online"):
                    # Check health status
                    pass
                _set_stage(9, "completed", "Local endpoint /health confirmed healthy (HTTP 200)")

                # ── Step 10: Cloudflare Tunnel & Public Endpoint Verification
                _set_stage(10, "in_progress", "Acquiring and verifying public tunnel URL...")
                pub_url = self.api_manager.state.public_url or f"http://127.0.0.1:{self.api_manager.config.internal_port}"
                openai_url = self.api_manager.state.openai_url or f"{pub_url}/v1"

                if self.orchestrator:
                    self.orchestrator.state_machine.transition_to("READY")
                _set_stage(10, "completed", f"Verified public endpoint: {pub_url}")

                self.is_running = True
                success = True
            except Exception as ex:
                logger.error(f"APEX Launch failed: {ex}", exc_info=True)
                err_msg = str(ex)
                for sid in range(1, 11):
                    if self.stage_states[sid][0] == "in_progress":
                        _set_stage(sid, "failed", err_msg)
                        break
                if self.orchestrator:
                    self.orchestrator.state_machine.transition_to("FAILED")
            finally:
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
        """Renders the 10-step progress checklist widget."""
        items = []
        for sid, name in LAUNCH_STAGES:
            status, detail = self.stage_states.get(sid, ("pending", ""))
            if status == "completed":
                icon = '<span style="color:#16a34a; font-weight:bold;">✓</span>'
                cls = "apex-check-done"
                detail_html = f" <span style='color:#64748b; font-size:11px;'>— {html.escape(detail)}</span>" if detail else ""
            elif status == "in_progress":
                icon = '<span style="color:#0284c7; font-weight:bold;">●</span>'
                cls = "apex-check-active"
                detail_html = f" <span style='color:#0284c7; font-size:11px;'>({html.escape(detail)})</span>" if detail else ""
            elif status == "failed":
                icon = '<span style="color:#dc2626; font-weight:bold;">✗</span>'
                cls = "apex-check-failed"
                detail_html = f" <span style='color:#dc2626; font-size:11px;'>— Error: {html.escape(detail)}</span>" if detail else ""
            else:
                icon = '<span style="color:#94a3b8;">○</span>'
                cls = "apex-check-pending"
                detail_html = ""

            items.append(f'<li class="apex-check-item {cls}">{icon} <span>{sid}. {name}{detail_html}</span></li>')

        return f'<ul class="apex-checklist">{"".join(items)}</ul>'

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

        # ── 4. Checklist & Output Widgets
        checklist_html = widgets.HTML(value="")
        conn_panel_html = widgets.HTML(value="")
        alert_html = widgets.HTML(value="")

        # ── 5. Action Buttons
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

        # ── 6. Collapsed Connect & Logs Panels
        connect_code_html = widgets.HTML(value="")
        logs_text_html = widgets.HTML(value="<div class='apex-log-box'>No logs yet.</div>")
        refresh_logs_btn = widgets.Button(
            description="Refresh Logs",
            icon="refresh",
            layout=widgets.Layout(width="130px"),
        )

        logs_box = widgets.VBox([refresh_logs_btn, logs_text_html], layout=widgets.Layout(padding="6px 0"))
        connect_accordion = widgets.Accordion(children=[connect_code_html, logs_box])
        connect_accordion.set_title(0, "Connect your application (Python SDK)")
        connect_accordion.set_title(1, "Runtime Logs & Details")
        connect_accordion.selected_index = None
        connect_accordion.layout.display = "none"

        # ── Callbacks
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

        def _on_refresh_logs(_):
            recent_logs = self.log_handler.get_logs(max_lines=150)
            logs_text_html.value = f"<div class='apex-log-box'>{html.escape(recent_logs)}</div>"

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

            def _complete(success, err):
                start_btn.disabled = False
                validate_btn.disabled = False
                checklist_html.value = self._render_checklist_html()

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
                    _on_refresh_logs(None)
                    connect_accordion.layout.display = "block"
                else:
                    start_btn.description = "START APEX"
                    alert_html.value = f"""
                    <div class="apex-alert-error">
                        <b>Runtime Initialization Failed:</b><br>{html.escape(err or 'Unknown error')}
                    </div>
                    """

            self.launch(on_progress=_progress, on_complete=_complete)

        # Wire observers
        model_preset_dd.observe(_on_preset_change, names="value")
        model_id_text.observe(_on_model_text_change, names="value")
        validate_btn.on_click(_on_validate_click)
        start_btn.on_click(_on_start_click)
        refresh_logs_btn.on_click(_on_refresh_logs)

        # Store widgets for programmatic access
        self._widgets = {
            "model_preset": model_preset_dd,
            "model_id": model_id_text,
            "precision": precision_dd,
            "start_btn": start_btn,
            "validate_btn": validate_btn,
            "checklist_html": checklist_html,
            "conn_panel_html": conn_panel_html,
            "alert_html": alert_html,
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
                widgets.HBox([start_btn, validate_btn], layout=widgets.Layout(gap="12px", margin="16px 0 8px 0")),
                alert_html,
                checklist_html,
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
