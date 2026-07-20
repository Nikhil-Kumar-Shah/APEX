"""Codebase launcher integrating system path loading and lifecycle runs."""

import sys
from pathlib import Path
from typing import Any, Optional


import logging
logger = logging.getLogger("bootstrap.launcher")

class RuntimeLauncher:
    """Configures system search paths, mounts lifecycles, and boots API servers and dashboards."""

    def __init__(self, repository_path: Path):
        """Initializes the RuntimeLauncher.

        Args:
            repository_path: The local directory of the cloned repository.
        """
        self.repository_path = repository_path.resolve()

    def configure_sys_path(self) -> None:
        """Ensures the repository path resides at the beginning of sys.path."""
        repo_str = str(self.repository_path)
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)
        else:
            # Shift to front to override local imports
            sys.path.remove(repo_str)
            sys.path.insert(0, repo_str)

    def launch(self) -> bool:
        """Imports the runtime package from the repository and boots the lifecycle.

        Returns:
            bool: True if initialization was successful.
        """
        self.configure_sys_path()

        # Dynamic import to execute from cloned repository path
        try:
            from runtime.core.lifecycle import RuntimeLifecycle
            from runtime.model.manager import ModelManager
            from runtime.core.health import HealthMonitor
            
            # 1. UI Registry and Dashboard Initialization (BEFORE Lifecycle)
            from runtime.ui import ui_registry
            ui_registry.load_all()
            dashboard_module = ui_registry.get_module("dashboard")

            dashboard = None
            if dashboard_module and hasattr(dashboard_module, "RuntimeDashboard"):
                dashboard = dashboard_module.RuntimeDashboard()
                dashboard.render()

                # Remove standard output streaming immediately so logs go purely to widget
                from runtime.logging.logger import remove_stream_handlers, logging
                remove_stream_handlers(logging.getLogger("runtime"))
                remove_stream_handlers(logging.getLogger("bootstrap"))

            logger.info(f"Launching runtime from: {self.repository_path}", extra={"prefix": "SYSTEM"})
            
            # 2. Start runtime lifecycle
            lifecycle = RuntimeLifecycle(workspace_path=self.repository_path)
            success = lifecycle.startup(interactive=False)
            if not success:
                logger.error("Runtime lifecycle startup failed.", extra={"prefix": "ERROR"})
                return False

            # 3. Initialize managers and bind to Dashboard
            cache_path = lifecycle.drive_manager.get_path("cache")
            model_mgr = ModelManager(cache_path)
            health_mon = HealthMonitor(cache_path, model_mgr)

            if dashboard:
                dashboard.bind_managers(
                    config_manager=lifecycle.config_manager,
                    model_manager=model_mgr,
                    health_monitor=health_mon,
                    lifecycle=lifecycle
                )
                dashboard.refresh()
            else:
                logger.warning("RuntimeDashboard UI module unavailable. Running headless.", extra={"prefix": "WARNING"})
            
            return True
        except ImportError as e:
            logger.error(f"Failed to import runtime package modules from {self.repository_path}: {e}", extra={"prefix": "ERROR"})
            return False
        except Exception as e:
            logger.error(f"Execution error during runtime launch: {e}", exc_info=True, extra={"prefix": "ERROR"})
            return False
