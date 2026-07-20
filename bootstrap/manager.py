"""Centralized Bootstrap Orchestrator."""

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from bootstrap.config import BootstrapConfig
from bootstrap.repository_manager import RepositoryManager
from bootstrap.dependency_manager import DependencyInstaller
from bootstrap.diagnostics import DiagnosticsManager
from bootstrap.launcher import RuntimeLauncher

logger = logging.getLogger("bootstrap.manager")


@dataclass
class RuntimeContext:
    """Encapsulates environment paths for bootstrap initialization."""
    environment: str
    persistence: Path
    runtime: Path


class BootstrapManager:
    """Single orchestrator that manages APEX initialization."""

    def __init__(self, context: RuntimeContext):
        self.config = BootstrapConfig()
        self.context = context

    def launch(self) -> None:
        """Executes the complete APEX bootstrap pipeline.
        
        Orchestrates: Repository -> Dependencies -> Diagnostics -> Workspace -> Runtime
        """
        logger.info("Initializing APEX Bootstrap Sequence...", extra={"prefix": "SYSTEM"})
        logger.info(f"Environment: {self.context.environment}", extra={"prefix": "SYSTEM"})
        logger.info(f"Runtime Path: {self.context.runtime}", extra={"prefix": "SYSTEM"})
        
        try:
            # 1. Repository Manager
            repo_manager = RepositoryManager(self.context.runtime, self.config.repo_url)
            
            if not repo_manager.is_cloned():
                if not repo_manager.clone():
                    raise RuntimeError("Failed to clone APEX repository.")
            else:
                # Update existing
                repo_manager.update()
                repo_manager.checkout(self.config.default_branch)

            if not repo_manager.validate_integrity():
                raise RuntimeError("Repository validation failed. Codebase may be corrupt.")
                
            # 2. Dependency Manager
            dep_installer = DependencyInstaller(self.context.runtime / "requirements.txt")
            if not dep_installer.install_requirements():
                logger.warning("Dependency installation returned warnings. Continuing anyway.", extra={"prefix": "WARNING"})
                
            # 3. Diagnostics
            diagnostics = DiagnosticsManager(self.context.runtime)
            diagnostics.run_diagnostics()

            # 4. Runtime Launcher
            logger.info("Starting APEX Runtime...", extra={"prefix": "SYSTEM"})
            launcher = RuntimeLauncher(self.context.runtime)
            if not launcher.launch():
                raise RuntimeError("Runtime initialization failed.")
                
        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, e: Exception) -> None:
        """Outputs a clean UI error boundary instead of a raw traceback."""
        try:
            from IPython.display import display, HTML
            html = f"""
            <div style="border: 1px solid #dc3545; border-radius: 4px; padding: 15px; margin: 15px 0; background: #fff8f8; font-family: sans-serif;">
                <h3 style="color: #dc3545; margin-top: 0;">❌ APEX Bootstrap Failed</h3>
                <p><b>Reason:</b> {str(e)}</p>
                <p><b>Suggested Fix:</b> Try factory resetting your runtime (Runtime > Disconnect and Delete Runtime) or ensuring Github is reachable.</p>
                <details>
                    <summary style="cursor: pointer; color: #6c757d; font-size: 0.9em;">Developer Details (Click to Expand)</summary>
                    <pre style="background: #f8f9fa; padding: 10px; margin-top: 10px; border-radius: 4px; overflow-x: auto; font-size: 0.85em;">{repr(e)}</pre>
                </details>
            </div>
            """
            display(HTML(html))
        except ImportError:
            pass
        
        logger.error(f"Bootstrap Failed: {e}", extra={"prefix": "ERROR"})
