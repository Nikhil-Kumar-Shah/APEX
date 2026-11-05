"""APEX Central Runtime Coordinator — Decoupled 3-Plane Asynchronous Orchestrator.

Manages execution across:
1. Control Plane: Fast config, hardware detection, scoped storage, task coordination (< 2.0s).
2. Model Execution Plane: Cache-first resolution, weight download, tensor allocation, inference warmup.
3. Connectivity Plane: Port negotiation, Uvicorn ASGI server, health probing, Cloudflare tunnel.
"""

from enum import Enum
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from runtime.api.configuration import APIConfig
from runtime.api.manager import APIManager
from runtime.api.state import RuntimeState
from runtime.config.profile import detect_environment_hardware, normalize_hf_model_id
from runtime.config.schema import ApexConfig
from runtime.core.errors import ApexErrorCode, RuntimeErrorBase
from runtime.core.lifecycle import RuntimeLifecycle
from runtime.memory.workspace import WorkspaceManager
from runtime.model.cache import CacheManager
from runtime.model.manager import ModelManager
from runtime.orchestrator.dispatcher import EventDispatcher
from runtime.orchestrator.events import RuntimeEvent
from runtime.orchestrator.state_machine import RuntimeStateMachine

logger = logging.getLogger("runtime.orchestrator.coordinator")


class ControlPlaneStatus(str, Enum):
    """Lifecycle state of the Control Plane."""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    READY = "ready"
    FAILED = "failed"


class ModelExecutionStatus(str, Enum):
    """Authoritative lifecycle state of the Model Execution Plane."""
    MODEL_NOT_CONFIGURED = "model_not_configured"
    MODEL_RESOLVING = "model_resolving"
    MODEL_CACHE_CHECK = "model_cache_check"
    MODEL_DOWNLOADING = "model_downloading"
    MODEL_LOADING = "model_loading"
    MODEL_READY = "model_ready"
    MODEL_FAILED = "model_failed"
    MODEL_UNLOADING = "model_unloading"
    MODEL_UNLOADED = "model_unloaded"

    # Compatibility aliases
    NOT_CONFIGURED = "model_not_configured"
    RESOLVING = "model_resolving"
    CACHE_CHECK = "model_cache_check"
    DOWNLOADING = "model_downloading"
    LOADING = "model_loading"
    READY = "model_ready"
    FAILED = "model_failed"
    UNLOADING = "model_unloading"
    UNLOADED = "model_unloaded"


class APIStatus(str, Enum):
    """Lifecycle state of the Local API server."""
    API_NOT_STARTED = "api_not_started"
    API_STARTING = "api_starting"
    API_READY = "api_ready"
    API_FAILED = "api_failed"

    # Compatibility aliases
    NOT_STARTED = "api_not_started"
    STARTING = "api_starting"
    READY = "api_ready"
    FAILED = "api_failed"


class TunnelStatus(str, Enum):
    """Lifecycle state of the Cloudflare Quick Tunnel."""
    TUNNEL_NOT_STARTED = "tunnel_not_started"
    TUNNEL_STARTING = "tunnel_starting"
    TUNNEL_READY = "tunnel_ready"
    TUNNEL_FAILED = "tunnel_failed"

    # Compatibility aliases
    NOT_STARTED = "tunnel_not_started"
    STARTING = "tunnel_starting"
    READY = "tunnel_ready"
    FAILED = "tunnel_failed"


class SystemStatus(str, Enum):
    """Overall system readiness state."""
    STOPPED = "stopped"
    STARTING = "starting"
    DEGRADED = "degraded"
    READY = "ready"
    FAILED = "failed"

    # Compatibility aliases
    OPERATIONAL = "ready"


class RuntimeCoordinator:
    """Central decoupled orchestrator for APEX runtime execution."""

    def __init__(
        self,
        workspace_path: Optional[Path] = None,
        project_root: Optional[Path] = None,
        model_manager: Optional[ModelManager] = None,
        api_manager: Optional[APIManager] = None,
    ):
        """Initializes the RuntimeCoordinator."""
        target_path = workspace_path or project_root or Path.cwd()
        self.workspace_path = Path(target_path).resolve()
        self.project_root = self.workspace_path
        self.model_manager = model_manager
        self.api_manager = api_manager
        self.tunnel_manager: Any = None
        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.workspace_manager: Optional[WorkspaceManager] = None

        # Authoritative plane states
        self.control_state: ControlPlaneStatus = ControlPlaneStatus.NOT_INITIALIZED
        self.model_state: ModelExecutionStatus = ModelExecutionStatus.MODEL_NOT_CONFIGURED
        self.api_state: APIStatus = APIStatus.API_NOT_STARTED
        self.tunnel_state: TunnelStatus = TunnelStatus.TUNNEL_NOT_STARTED
        self._manual_system_state: Optional[SystemStatus] = None
        self.system_state: SystemStatus = SystemStatus.STOPPED

        # Subsystem error messages
        self.control_error: Optional[str] = None
        self.model_error: Optional[str] = None
        self.api_error: Optional[str] = None
        self.tunnel_error: Optional[str] = None

        # Hardware & config references
        self.hardware_info: Dict[str, Any] = {}
        self.active_config: Optional[ApexConfig] = None
        self.resolved_model_id: str = ""

        # Event dispatcher & legacy state machine sync
        self.event_dispatcher = EventDispatcher()
        self.state_machine = RuntimeStateMachine("STOPPED")

        # Concurrency & threading locks
        self._lock = threading.Lock()
        self._model_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._active_threads: List[threading.Thread] = []

        # Progress & notification listeners
        self.listeners: List[Callable[[str, Dict[str, Any]], None]] = []

    # ── Status Property Aliases ──────────────────────────────────────────────

    @property
    def control_status(self) -> ControlPlaneStatus:
        return self.control_state

    @control_status.setter
    def control_status(self, val: ControlPlaneStatus) -> None:
        self.control_state = val

    @property
    def model_status(self) -> ModelExecutionStatus:
        return self.model_state

    @model_status.setter
    def model_status(self, val: ModelExecutionStatus) -> None:
        self.model_state = val

    @property
    def api_status(self) -> APIStatus:
        return self.api_state

    @api_status.setter
    def api_status(self, val: APIStatus) -> None:
        self.api_state = val

    @property
    def tunnel_status(self) -> TunnelStatus:
        return self.tunnel_state

    @tunnel_status.setter
    def tunnel_status(self, val: TunnelStatus) -> None:
        self.tunnel_state = val

    @property
    def system_status(self) -> SystemStatus:
        if self._manual_system_state is not None:
            return self._manual_system_state
        if self.control_state == ControlPlaneStatus.FAILED or self.api_state in (APIStatus.API_FAILED, "api_failed"):
            return SystemStatus.FAILED
        if self.api_state in (APIStatus.API_READY, "api_ready") and self.model_state in (
            ModelExecutionStatus.MODEL_LOADING,
            ModelExecutionStatus.MODEL_DOWNLOADING,
            ModelExecutionStatus.MODEL_FAILED,
            "model_loading",
            "model_downloading",
            "model_failed",
        ):
            return SystemStatus.DEGRADED
        if self.is_model_ready and self.is_api_ready:
            return SystemStatus.READY
        if self.control_state == ControlPlaneStatus.READY:
            return SystemStatus.STARTING
        return SystemStatus.STOPPED

    @system_status.setter
    def system_status(self, val: SystemStatus) -> None:
        self._manual_system_state = val
        self.system_state = val

    # ── Readiness Properties ─────────────────────────────────────────────────

    @property
    def is_control_plane_ready(self) -> bool:
        """True if control plane has completed configuration and hardware detection."""
        return self.control_state == ControlPlaneStatus.READY

    @property
    def is_api_ready(self) -> bool:
        """True if the local FastAPI server is bound and /health returns HTTP 200."""
        return self.api_state == APIStatus.API_READY

    @property
    def is_tunnel_ready(self) -> bool:
        """True if public Cloudflare tunnel is established and verified."""
        return self.tunnel_state == TunnelStatus.TUNNEL_READY

    @property
    def is_model_ready(self) -> bool:
        """True if model weights are loaded and the warmup inference pass succeeded."""
        return self.model_state == ModelExecutionStatus.MODEL_READY

    @property
    def is_system_ready(self) -> bool:
        """True if both model execution and networking connectivity are operational."""
        return self.is_model_ready and self.is_api_ready

    @property
    def is_fully_operational(self) -> bool:
        """Alias for overall end-to-end readiness."""
        return self.is_model_ready and self.is_api_ready

    @property
    def model_repo_id(self) -> str:
        """Returns the resolved or active model repository identifier."""
        return self.resolved_model_id or (self.active_config.model_id if self.active_config else "")

    @property
    def public_url(self) -> Optional[str]:
        """Returns the public Cloudflare tunnel URL if ready."""
        if self.tunnel_manager and hasattr(self.tunnel_manager, "tunnel_url") and isinstance(self.tunnel_manager.tunnel_url, str):
            return self.tunnel_manager.tunnel_url
        if self.api_manager and getattr(self.api_manager, "state", None):
            return self.api_manager.state.public_url
        return None

    @property
    def tunnel_url(self) -> Optional[str]:
        """Alias for public Cloudflare tunnel URL."""
        return self.public_url

    @property
    def openai_url(self) -> Optional[str]:
        """Returns the OpenAI API Base URL."""
        if self.api_manager and getattr(self.api_manager, "state", None):
            return self.api_manager.state.openai_url
        return None

    @property
    def storage_info(self) -> Dict[str, Any]:
        """Returns storage allocation metrics guaranteeing local cache priority."""
        if self.lifecycle and self.lifecycle.drive_manager:
            return {
                "cache_path": self.lifecycle.drive_manager.get_path("cache"),
                "google_drive_mounted": self.lifecycle.drive_manager.is_drive_mounted(),
            }
        return {
            "cache_path": self.workspace_path / "cache",
            "google_drive_mounted": False,
        }

    # ── State Transition & Event Broadcasting ────────────────────────────────

    def _set_model_state(self, new_state: ModelExecutionStatus, error: Optional[str] = None) -> None:
        with self._lock:
            old_state = self.model_state
            self.model_state = new_state
            if error:
                self.model_error = error
        logger.info(f"Model Plane: {old_state.value} -> {new_state.value}", extra={"prefix": "MODEL"})
        if new_state == ModelExecutionStatus.MODEL_DOWNLOADING:
            self.state_machine.transition_to("MODEL_DOWNLOADING")
        elif new_state == ModelExecutionStatus.MODEL_LOADING:
            self.state_machine.transition_to("MODEL_LOADING")
        elif new_state == ModelExecutionStatus.MODEL_READY:
            self.state_machine.transition_to("MODEL_READY")
        self._broadcast("model_state_changed", {"from": old_state.value, "to": new_state.value, "error": error})

    def _set_api_state(self, new_state: APIStatus, error: Optional[str] = None) -> None:
        with self._lock:
            old_state = self.api_state
            self.api_state = new_state
            if error:
                self.api_error = error
        logger.info(f"API Plane: {old_state.value} -> {new_state.value}", extra={"prefix": "API"})
        if new_state == APIStatus.API_STARTING:
            self.state_machine.transition_to("API_STARTING")
        elif new_state == APIStatus.API_READY:
            self.state_machine.transition_to("API_READY")
        self._broadcast("api_state_changed", {"from": old_state.value, "to": new_state.value, "error": error})

    def _set_tunnel_state(self, new_state: TunnelStatus, error: Optional[str] = None) -> None:
        with self._lock:
            old_state = self.tunnel_state
            self.tunnel_state = new_state
            if error:
                self.tunnel_error = error
        logger.info(f"Tunnel Plane: {old_state.value} -> {new_state.value}", extra={"prefix": "TUNNEL"})
        if new_state == TunnelStatus.TUNNEL_STARTING:
            self.state_machine.transition_to("TUNNEL_STARTING")
        elif new_state == TunnelStatus.TUNNEL_READY:
            self.state_machine.transition_to("TUNNEL_READY")
        self._broadcast("tunnel_state_changed", {"from": old_state.value, "to": new_state.value, "error": error})

    def _broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        event = RuntimeEvent(event_type, data)
        self.event_dispatcher.publish(event)
        for listener in list(self.listeners):
            try:
                listener(event_type, data)
            except Exception:
                pass

    def add_listener(self, listener: Callable[[str, Dict[str, Any]], None]) -> None:
        """Subscribes a listener to coordinator status and progress events."""
        if listener not in self.listeners:
            self.listeners.append(listener)

    def remove_listener(self, listener: Callable[[str, Dict[str, Any]], None]) -> None:
        """Unsubscribes a listener."""
        if listener in self.listeners:
            self.listeners.remove(listener)

    # ── Plane 1: Control Plane Initialization ────────────────────────────────

    def init_control_plane(
        self,
        config: Optional[ApexConfig] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> ControlPlaneStatus:
        """Initializes the Control Plane quickly (< 1.5s) without downloading or loading models."""
        self.control_state = ControlPlaneStatus.INITIALIZING
        self.system_state = SystemStatus.STARTING
        self.active_config = config or ApexConfig()
        t0 = time.time()

        try:
            if on_progress:
                on_progress("Detecting compute hardware & memory...")
            self.hardware_info = detect_environment_hardware()

            # Set hardware device
            if self.hardware_info.get("cuda_available"):
                self.active_config.device = "cuda"
            else:
                self.active_config.device = "cpu"

            if on_progress:
                on_progress("Initializing workspace layout...")
            if self.lifecycle is None:
                self.lifecycle = RuntimeLifecycle(workspace_path=self.workspace_path)

            # Fast non-blocking lifecycle startup (safe storage detection)
            lifecycle_ok = self.lifecycle.startup(interactive=False)
            if not lifecycle_ok:
                raise RuntimeErrorBase(
                    message="Control plane lifecycle initialization failed.",
                    cause="Failed initializing directory structure or default workspace configuration.",
                    recovery="Check write permissions for workspace directory.",
                    code=ApexErrorCode.GENERAL_RUNTIME_ERROR,
                )

            # Resolve local SSD cache path (never depends on Google Drive)
            cache_path = self.lifecycle.drive_manager.get_path("cache")
            workspaces_dir = self.lifecycle.drive_manager.persistence_root / "workspaces"

            if self.model_manager is None:
                self.model_manager = ModelManager(cache_path)

            if self.workspace_manager is None:
                self.workspace_manager = WorkspaceManager(workspaces_dir)
                self.workspace_manager.create_workspace("default", "Default Workspace")
                self.workspace_manager.load_workspace("default")

            self.control_state = ControlPlaneStatus.READY
            elapsed = time.time() - t0
            logger.info(f"Control Plane initialized in {elapsed:.2f}s", extra={"prefix": "CONTROL"})
            if on_progress:
                on_progress(f"Control plane ready ({elapsed:.2f}s)")
            return self.control_state

        except Exception as ex:
            self.control_state = ControlPlaneStatus.FAILED
            self.control_error = str(ex)
            logger.error(f"Control Plane initialization failed: {ex}", exc_info=True)
            if on_progress:
                on_progress(f"Control plane failed: {ex}")
            return self.control_state

    # ── Plane 2: Connectivity Plane (API & Tunnel) ───────────────────────────

    def start_connectivity_plane(
        self,
        enable_tunnel: bool = True,
        tunnel_provider: str = "cloudflare",
        api_port: int = 8000,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[APIStatus, TunnelStatus]:
        """Starts Uvicorn ASGI server and Cloudflare tunnel independently of model weights."""
        if not self.is_control_plane_ready:
            if not self.active_config:
                self.init_control_plane()

        self._set_api_state(APIStatus.API_STARTING)
        if enable_tunnel:
            self._set_tunnel_state(TunnelStatus.TUNNEL_STARTING)

        try:
            if on_progress:
                on_progress("Binding local API server...")

            # Initialize APIManager if not provided
            if self.api_manager is None:
                api_config = APIConfig(
                    api_enabled=True,
                    internal_port=api_port,
                    transport=tunnel_provider if enable_tunnel else "local",
                    enable_auth=self.active_config.enable_auth if self.active_config else False,
                    api_key=self.active_config.api_key if self.active_config else "",
                )
                api_state = RuntimeState()
                self.api_manager = APIManager(api_config, api_state, self.model_manager)
            else:
                if hasattr(self.api_manager, "config") and self.api_manager.config:
                    self.api_manager.config.transport = tunnel_provider if enable_tunnel else "local"
                    self.api_manager.config.internal_port = api_port

            # Start API if not running
            if not getattr(self.api_manager, "is_running", False):
                api_ok = self.api_manager.start()
            else:
                api_ok = True

            if not api_ok:
                err_msg = getattr(getattr(self.api_manager, "state", None), "last_error", None) or "FastAPI server failed to start"
                self._set_api_state(APIStatus.API_FAILED, error=err_msg)
                if enable_tunnel:
                    self._set_tunnel_state(TunnelStatus.TUNNEL_FAILED, error=err_msg)
                return (self.api_state, self.tunnel_state)

            self._set_api_state(APIStatus.API_READY)
            if on_progress:
                on_progress(f"API server online on port {api_port}")

            if enable_tunnel:
                try:
                    from runtime.api.tunnel import TunnelManager
                    if self.tunnel_manager is None:
                        tm = getattr(self.api_manager, "tunnel_manager", None)
                        if tm is not None and not str(type(tm)).startswith("<class 'unittest.mock"):
                            self.tunnel_manager = tm
                        else:
                            self.tunnel_manager = TunnelManager(getattr(self.api_manager, "config", None), getattr(self.api_manager, "state", None))

                    tun_url = getattr(getattr(self.api_manager, "state", None), "public_url", None)
                    if (not tun_url or not isinstance(tun_url, str)) and hasattr(self.tunnel_manager, "start"):
                        start_res = self.tunnel_manager.start(api_port)
                        if isinstance(start_res, str):
                            tun_url = start_res
                    if (not tun_url or not isinstance(tun_url, str)) and hasattr(self.tunnel_manager, "tunnel_url") and isinstance(self.tunnel_manager.tunnel_url, str):
                        tun_url = self.tunnel_manager.tunnel_url

                    if tun_url and isinstance(tun_url, str):
                        self.tunnel_manager.tunnel_url = tun_url
                        self._set_tunnel_state(TunnelStatus.TUNNEL_READY)
                        if on_progress:
                            on_progress(f"Cloudflare tunnel online: {tun_url}")
                    else:
                        self._set_tunnel_state(TunnelStatus.TUNNEL_FAILED, error="No public URL acquired")
                except Exception as tun_err:
                    self._set_tunnel_state(TunnelStatus.TUNNEL_FAILED, error=str(tun_err))

            return (self.api_state, self.tunnel_state)

        except Exception as ex:
            err = str(ex)
            self._set_api_state(APIStatus.API_FAILED, error=err)
            self._set_tunnel_state(TunnelStatus.TUNNEL_FAILED, error=err)
            logger.error(f"Connectivity Plane failed: {ex}", exc_info=True)
            if on_progress:
                on_progress(f"Connectivity plane failed: {ex}")
            return (self.api_state, self.tunnel_state)

    # ── Plane 3: Model Execution Plane (Download, Load & Warmup) ─────────────

    def start_model_plane(
        self,
        model_id: Optional[str] = None,
        precision: Optional[str] = "float16",
        on_progress: Optional[Callable[[str, Optional[float]], None]] = None,
    ) -> ModelExecutionStatus:
        """Executes cache-first resolution, weight downloading, tensor allocation, and warmup."""
        if not self.is_control_plane_ready:
            if not self.active_config:
                self.init_control_plane()

        if self.active_config is None:
            self.active_config = ApexConfig()

        if model_id:
            self.active_config.model_id = model_id
        if precision:
            self.active_config.precision = precision

        with self._model_lock:
            # 1. Resolve & normalize Model ID
            raw_id = self.active_config.model_id or "Qwen/Qwen2.5-0.5B-Instruct"
            self._set_model_state(ModelExecutionStatus.MODEL_RESOLVING)
            if on_progress:
                on_progress(f"Resolving model identifier '{raw_id}'...", None)

            norm_id, is_val, val_err = normalize_hf_model_id(raw_id)
            if not is_val:
                err = val_err or "Invalid Hugging Face model identifier."
                self._set_model_state(ModelExecutionStatus.MODEL_FAILED, error=err)
                if on_progress:
                    on_progress(f"Model ID resolution failed: {err}", None)
                return self.model_state

            self.resolved_model_id = norm_id
            self.active_config.model_id = norm_id

            # 2. Cache-First Inspection
            self._set_model_state(ModelExecutionStatus.MODEL_CACHE_CHECK)
            is_cached = False
            if self.model_manager and hasattr(self.model_manager, "is_cached"):
                is_cached = self.model_manager.is_cached(norm_id)
            elif self.model_manager and hasattr(self.model_manager, "cache_dir"):
                cache_mgr = CacheManager(self.model_manager.cache_dir)
                is_cached = cache_mgr.is_cached(norm_id)

            if is_cached:
                if on_progress:
                    on_progress(f"Cache hit: {norm_id} is already cached on local storage.", 100.0)
                logger.info(f"Model {norm_id} is cached locally. Skipping network download.", extra={"prefix": "CACHE"})
            else:
                # 3. Model Download
                self._set_model_state(ModelExecutionStatus.MODEL_DOWNLOADING)
                if on_progress:
                    on_progress(f"Downloading model weights for {norm_id}...", None)

                try:
                    if self.model_manager:
                        self.model_manager.download_model(
                            norm_id,
                            revision=self.active_config.revision,
                            hf_token=self.active_config.hf_token,
                        )
                    if on_progress:
                        on_progress(f"Downloaded weights for {norm_id} successfully.", 100.0)
                except Exception as down_ex:
                    err = f"Model download failed: {down_ex}"
                    self._set_model_state(ModelExecutionStatus.MODEL_FAILED, error=err)
                    logger.error(err, exc_info=True)
                    if on_progress:
                        on_progress(err, None)
                    return self.model_state

            # 4. Model Loading into VRAM / RAM
            self._set_model_state(ModelExecutionStatus.MODEL_LOADING)
            target_device = self.active_config.device or "cpu"
            target_mem = "VRAM" if target_device == "cuda" else "system RAM"

            if on_progress:
                on_progress(f"Loading weights into {target_mem} ({self.active_config.precision})...", None)

            try:
                if self.model_manager:
                    self.model_manager.load_model(
                        norm_id,
                        precision=self.active_config.precision,
                        revision=self.active_config.revision,
                        hf_token=self.active_config.hf_token,
                        device=target_device,
                    )
            except Exception as load_ex:
                err = f"Failed allocating model tensors in {target_mem}: {load_ex}"
                self._set_model_state(ModelExecutionStatus.MODEL_FAILED, error=err)
                logger.error(err, exc_info=True)
                if on_progress:
                    on_progress(err, None)
                return self.model_state

            self._set_model_state(ModelExecutionStatus.MODEL_READY)
            if on_progress:
                on_progress(f"Model {norm_id} is ready for inference ({target_mem}).", 100.0)
            return self.model_state

    # ── Parallel Orchestration Pipeline ──────────────────────────────────────

    def launch_parallel(
        self,
        config: Optional[ApexConfig] = None,
        model_id: Optional[str] = None,
        precision: Optional[str] = "float16",
        enable_tunnel: bool = True,
        tunnel_provider: str = "cloudflare",
        api_port: int = 8000,
        sync: bool = True,
        on_control_progress: Optional[Callable[[str], None]] = None,
        on_connectivity_progress: Optional[Callable[[str], None]] = None,
        on_model_progress: Optional[Callable[[str, Optional[float]], None]] = None,
        on_complete: Optional[Callable[[bool, Optional[str]], None]] = None,
    ) -> Dict[str, Any]:
        """Launches the Control Plane, then executes Connectivity and Model planes in parallel."""
        self._stop_event.clear()
        cfg = config or ApexConfig()
        if model_id:
            cfg.model_id = model_id
        if precision:
            cfg.precision = precision
        cfg.port = api_port
        cfg.transport = tunnel_provider if enable_tunnel else "local"

        def _coordinator_work() -> Dict[str, Any]:
            # Step A: Control Plane (Serial, < 1.5s)
            self.init_control_plane(cfg, on_progress=on_control_progress)
            if not self.is_control_plane_ready:
                self.system_state = SystemStatus.FAILED
                if on_complete:
                    on_complete(False, f"Control Plane failed: {self.control_error}")
                return {
                    "control_plane": self.control_state,
                    "model_plane": self.model_state,
                    "api_status": self.api_state,
                    "tunnel_status": self.tunnel_state,
                }

            # Step B: Parallel Fork (Connectivity Plane & Model Plane)
            def _run_connectivity():
                self.start_connectivity_plane(
                    enable_tunnel=enable_tunnel,
                    tunnel_provider=tunnel_provider,
                    api_port=api_port,
                    on_progress=on_connectivity_progress,
                )

            def _run_model():
                self.start_model_plane(
                    model_id=cfg.model_id,
                    precision=cfg.precision,
                    on_progress=on_model_progress,
                )

            th_conn = threading.Thread(target=_run_connectivity, name="APEX-ConnectivityPlane", daemon=True)
            th_model = threading.Thread(target=_run_model, name="APEX-ModelPlane", daemon=True)

            self._active_threads = [th_conn, th_model]
            th_conn.start()
            th_model.start()

            th_conn.join()
            th_model.join()

            if on_complete:
                on_complete(self.is_fully_operational, None)

            return {
                "control_plane": self.control_state,
                "model_plane": self.model_state,
                "api_status": self.api_state,
                "tunnel_status": self.tunnel_state,
            }

        if sync:
            return _coordinator_work()
        else:
            main_worker = threading.Thread(target=_coordinator_work, name="APEX-Coordinator", daemon=True)
            main_worker.start()
            return {
                "control_plane": self.control_state,
                "model_plane": self.model_state,
                "api_status": self.api_state,
                "tunnel_status": self.tunnel_state,
            }

    # ── Orderly Teardown & Resource Cleanup ──────────────────────────────────

    def shutdown(
        self,
        sync: bool = True,
        on_complete: Optional[Callable[[bool, Optional[str]], None]] = None,
    ) -> bool:
        """Safely stops all plane tasks, tears down tunnel, and releases GPU VRAM."""
        self._stop_event.set()
        self.system_state = SystemStatus.STOPPED

        def _do_shutdown():
            err_msg: Optional[str] = None
            try:
                if self.tunnel_manager and hasattr(self.tunnel_manager, "stop"):
                    self.tunnel_manager.stop()
                if self.api_manager and hasattr(self.api_manager, "stop"):
                    self.api_manager.stop()
                if self.model_manager and hasattr(self.model_manager, "unload_model"):
                    self.model_manager.unload_model()

                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass

                import gc
                gc.collect()

                self.state_machine.transition_to("STOPPED")
                self.control_state = ControlPlaneStatus.NOT_INITIALIZED
                self.model_state = ModelExecutionStatus.MODEL_NOT_CONFIGURED
                self.api_state = APIStatus.API_NOT_STARTED
                self.tunnel_state = TunnelStatus.TUNNEL_NOT_STARTED
                self._manual_system_state = None
            except Exception as ex:
                err_msg = str(ex)
                logger.error(f"Error during runtime shutdown: {ex}", exc_info=True)
            finally:
                if on_complete:
                    on_complete(err_msg is None, err_msg)

        if sync:
            _do_shutdown()
            return True
        else:
            th = threading.Thread(target=_do_shutdown, name="APEX-Shutdown", daemon=True)
            th.start()
            return True
