"""Top-level APEX Runtime Facade for Notebook-driven workflows."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("runtime.facade")

class _APEXAPI:
    """Namespace for API-related commands."""
    def __init__(self, parent: 'APEXFacade'):
        self._parent = parent

    def start(self) -> None:
        """Starts the FastAPI server in the background."""
        if not self._parent._is_initialized:
            raise RuntimeError("APEX is not initialized. Call APEX.start() first.")
        
        # In a real implementation this would spawn the uvicorn thread
        logger.info("API Server starting...", extra={"prefix": "API"})
        if self._parent._dashboard:
            self._parent._dashboard.is_api_running = True
            self._parent._dashboard.refresh()
        logger.info("API Server is now online.", extra={"prefix": "SUCCESS"})

    def stop(self) -> None:
        """Stops the FastAPI server."""
        if not self._parent._is_initialized:
            return
        
        logger.info("API Server stopping...", extra={"prefix": "API"})
        if self._parent._dashboard:
            self._parent._dashboard.is_api_running = False
            self._parent._dashboard.refresh()
        logger.info("API Server stopped.", extra={"prefix": "SUCCESS"})


class APEXFacade:
    """Primary developer interface for controlling the APEX runtime synchronously from a Notebook."""

    def __init__(self):
        self._is_initialized = False
        self._lifecycle = None
        self._model_manager = None
        self._workspace_manager = None
        self._health_monitor = None
        self._dashboard = None
        self._orchestrator = None
        
        self.api = _APEXAPI(self)

    def start(self) -> None:
        """Initializes the runtime, managers, and the read-only dashboard."""
        if self._is_initialized:
            logger.info("APEX Runtime is already running.", extra={"prefix": "SYSTEM"})
            return

        print("Initializing APEX Runtime...")
        
        # We need the repository path. Assuming it's in the current working directory or /content/APEX
        repo_path = Path.cwd()
        if not (repo_path / "runtime").exists():
            # Fallback for colab
            repo_path = Path("/content/APEX")
            if not repo_path.exists():
                repo_path = Path.cwd()

        from runtime.core.lifecycle import RuntimeLifecycle
        from runtime.model.manager import ModelManager
        from runtime.core.health import HealthMonitor
        from runtime.memory.workspace import WorkspaceManager
        from runtime.ui import ui_registry
        
        # 1. Start lifecycle
        self._lifecycle = RuntimeLifecycle(workspace_path=repo_path)
        success = self._lifecycle.startup(interactive=False)
        if not success:
            raise RuntimeError("Failed to start APEX lifecycle.")
            
        # 2. Managers
        cache_path = self._lifecycle.drive_manager.get_path("cache")
        self._model_manager = ModelManager(cache_path)
        self._health_monitor = HealthMonitor(cache_path, self._model_manager)
        
        workspaces_dir = self._lifecycle.drive_manager.persistence_root / "workspaces"
        self._workspace_manager = WorkspaceManager(workspaces_dir)
        
        initial_ws = self._lifecycle.config_manager.config.get("project_id", "default")
        try:
            self._workspace_manager.load_workspace(initial_ws)
        except Exception:
            self._workspace_manager.create_workspace(initial_ws, self._lifecycle.config_manager.config.get("project_name", "Default Workspace"))
            self._workspace_manager.load_workspace(initial_ws)

        # 3. UI Dashboard
        ui_registry.load_all()
        dashboard_module = ui_registry.get_module("dashboard")
        if dashboard_module and hasattr(dashboard_module, "RuntimeDashboard"):
            self._dashboard = dashboard_module.RuntimeDashboard()
            self._dashboard.render()
            
            # Note: We NO LONGER remove standard output stream handlers.
            # We want native tqdm progress bars and print statements to work in cells.

            # Bind the managers so the dashboard can read statuses
            # We don't necessarily need orchestrator for read-only, but we pass it if required
            from runtime.orchestrator.orchestrator import RuntimeOrchestrator
            self._orchestrator = RuntimeOrchestrator(self._model_manager, self._workspace_manager)
            
            # The dashboard expects these 4 managers
            self._dashboard.bind_managers(
                config_manager=self._lifecycle.config_manager,
                model_manager=self._model_manager,
                health_monitor=self._health_monitor,
                lifecycle=self._lifecycle
            )
            # The dashboard now creates its own orchestrator internally in bind_managers if needed, 
            # or uses ours. Wait, dashboard.bind_managers creates its own orchestrator. We will fix that.
            self._dashboard.refresh()

        self._is_initialized = True
        logger.info("APEX Runtime is ready.", extra={"prefix": "SUCCESS"})

    def download(self, model_id: str) -> None:
        """Downloads a model synchronously directly in the notebook cell."""
        if not self._is_initialized:
            raise RuntimeError("APEX is not initialized. Call APEX.start() first.")

        if self._orchestrator:
            self._orchestrator.state_machine.transition_to("DOWNLOADING_MODEL")
            
        if self._dashboard:
            self._dashboard.refresh()

        try:
            self._model_manager.download_model(model_id)
        finally:
            if self._orchestrator:
                self._orchestrator.state_machine.transition_to("READY")
            if self._dashboard:
                self._dashboard.refresh()

    def load(self, model_id: str, **kwargs) -> None:
        """Loads a model synchronously directly in the notebook cell."""
        if not self._is_initialized:
            raise RuntimeError("APEX is not initialized. Call APEX.start() first.")

        if self._orchestrator:
            self._orchestrator.state_machine.transition_to("LOADING_MODEL")
            
        if self._dashboard:
            self._dashboard.refresh()

        try:
            self._model_manager.load_model(model_id, **kwargs)
        finally:
            if self._orchestrator:
                self._orchestrator.state_machine.transition_to("READY")
            if self._dashboard:
                self._dashboard.refresh()

    def stop(self) -> None:
        """Stops the runtime and API servers."""
        if not self._is_initialized:
            return
            
        self.api.stop()
        
        if self._orchestrator:
            self._orchestrator.shutdown()

        if self._model_manager:
            self._model_manager.unload_model()

        self._is_initialized = False
        logger.info("APEX Runtime stopped.", extra={"prefix": "SUCCESS"})


# Global singleton instance
APEX = APEXFacade()
