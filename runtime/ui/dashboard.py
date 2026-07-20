"""Minimal side-by-side interactive dashboard for Google Colab — APEX V1."""

import logging
from pathlib import Path
from typing import Any, Optional

from runtime.config.manager import ConfigManager
from runtime.core.health import HealthMonitor
from runtime.model.manager import ModelManager
from runtime.memory.workspace import WorkspaceManager

# Pull the global widget handler to bind our UI console
from runtime.logging.logger import get_widget_handler

logger = logging.getLogger("runtime.ui.dashboard")


def get_minimal_css() -> str:
    """Returns clean, minimal developer theme CSS."""
    return """
    <style>
        .apex-dash {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            background-color: #f8f9fa;
            color: #212529;
            font-size: 13px;
        }
        .apex-left-panel {
            width: 25%;
            border-right: 2px solid #dee2e6;
            padding-right: 15px;
            margin-right: 15px;
        }
        .apex-right-panel {
            width: 75%;
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 10px;
            border-radius: 4px;
            font-family: "Courier New", monospace;
            height: 500px;
            overflow-y: auto;
        }
        .apex-nav {
            display: flex;
            flex-direction: column;
            gap: 5px;
            margin-bottom: 15px;
            border-bottom: 1px solid #dee2e6;
            padding-bottom: 10px;
        }
        .apex-btn {
            background-color: #e9ecef;
            border: 1px solid #ced4da;
            padding: 6px 10px;
            cursor: pointer;
            border-radius: 4px;
            color: #495057;
            font-weight: bold;
            text-align: left;
        }
        .apex-btn:hover { background-color: #dee2e6; }
        .apex-card {
            background: white;
            border: 1px solid #dee2e6;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 10px;
        }
        .apex-header {
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 10px;
            color: #0d6efd;
        }
        .apex-hint {
            color: #6c757d;
            font-size: 11px;
            margin-top: 4px;
        }
    </style>
    """


class RuntimeDashboard:
    """Side-by-side developer control panel (Left: Controls, Right: Terminal Output).

    APEX V1 UI Constraints:
        - Four tabs only: Status, Workspace, Model, Runtime
        - Model tab: single HF Model ID input + Download + Load/Unload
        - No engine selectors, no GGUF, no quantization controls
    """

    def __init__(self):
        """Initializes an empty dashboard (bind_managers must be called later)."""
        self.config_manager: Optional[ConfigManager] = None
        self.model_manager: Optional[ModelManager] = None
        self.health_monitor: Optional[HealthMonitor] = None
        self.lifecycle: Optional[Any] = None
        self.workspace_manager: Optional[WorkspaceManager] = None
        self.orchestrator: Optional[Any] = None
        self.is_api_running = False
        
        self.left_controls: Optional[Any] = None

    def bind_managers(
        self,
        config_manager: ConfigManager,
        model_manager: ModelManager,
        health_monitor: HealthMonitor,
        lifecycle: Any,
        orchestrator: Any = None
    ):
        """Binds backend managers and updates the dashboard."""
        self.config_manager = config_manager
        self.model_manager = model_manager
        self.health_monitor = health_monitor
        self.lifecycle = lifecycle
        
        workspaces_dir = self.lifecycle.drive_manager.persistence_root / "workspaces"
        self.workspace_manager = WorkspaceManager(workspaces_dir)
        
        initial_ws = config_manager.config.get("project_id", "default")
        try:
            self.workspace_manager.load_workspace(initial_ws)
        except Exception:
            self.workspace_manager.create_workspace(initial_ws, config_manager.config.get("project_name", "Default Workspace"))
            self.workspace_manager.load_workspace(initial_ws)

        self.orchestrator = orchestrator

    def render(self) -> Any:
        """Renders the dashboard skeleton and binds the logging widget."""
        try:
            import ipywidgets as widgets
            from IPython.display import display, HTML
        except ImportError:
            logger.info("Headless rendering: ipywidgets is not installed.", extra={"prefix": "SYSTEM"})
            return "Headless Dashboard Instance"

        display(widgets.HTML(get_minimal_css()))

        # Layout containers
        self.left_controls = widgets.Output()
        self.left_controls.add_class('apex-left-panel')
        
        right_console = widgets.Output()
        right_console.add_class('apex-right-panel')

        # Bind the global logger to this right_console widget BEFORE anything else
        widget_handler = get_widget_handler()
        widget_handler.set_widget(right_console)

        # Navigation Buttons (Vertical) — V1: exactly 4 tabs
        buttons = {
            "status": widgets.Button(description="Status", layout=widgets.Layout(width='100%')),
            "workspace": widgets.Button(description="Workspace", layout=widgets.Layout(width='100%')),
            "models": widgets.Button(description="Model", layout=widgets.Layout(width='100%')),
            "runtime": widgets.Button(description="Runtime", layout=widgets.Layout(width='100%')),
        }

        def show_status(b=None):
            if not self.orchestrator:
                return
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "status" else ""
            
            with self.left_controls:
                self.left_controls.clear_output()
                report = self.health_monitor.generate_report()
                active_model = report["model_manager"].get("active_model_id") or "None"
                api_status = "Online" if getattr(self, 'is_api_running', False) else "Offline"
                worker_alive = self.orchestrator.worker.is_alive() if self.orchestrator else False
                active_tasks = self.orchestrator.task_queue.list_tasks() if self.orchestrator else []
                state = self.orchestrator.state_machine.current_state if self.orchestrator else "UNKNOWN"
                
                html = f"""
                <div class="apex-header">Status</div>
                <div class="apex-card">
                    <b>State:</b> {state}<br>
                    <b>Workspace:</b> {self.workspace_manager.active_workspace_id}<br>
                    <b>Model:</b> {active_model.split('/')[-1]}<br>
                    <b>GPU:</b> {report['gpu'].get('device_name') or 'CPU Fallback'}<br>
                    <b>API:</b> {api_status}<br>
                    <hr>
                    <b>Worker:</b> {'ALIVE' if worker_alive else 'DEAD'}<br>
                    <b>Queue:</b> {len(active_tasks)} tasks
                </div>
                """
                display(HTML(html))

        def show_workspace(b=None):
            if not self.orchestrator:
                return
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "workspace" else ""
            
            with self.left_controls:
                self.left_controls.clear_output()
                display(HTML("<div class='apex-header'>Workspace</div>"))
                
                ws_list = self.workspace_manager.list_workspaces() if self.workspace_manager else []
                ws_options = [(w["name"], w["workspace_id"]) for w in ws_list]
                active_ws = self.workspace_manager.active_workspace_id if self.workspace_manager else "default"
                
                html = f"<div><b>Active Workspace:</b> {active_ws}</div><ul>"
                for name, wid in ws_options:
                    html += f"<li>{name} ({wid})</li>"
                html += "</ul>"
                display(HTML(html))

        def show_models(b=None):
            if not self.orchestrator:
                return
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "models" else ""
            
            with self.left_controls:
                self.left_controls.clear_output()
                display(HTML("<div class='apex-header'>Model</div>"))
                
                # Read-only model list
                cached = self.model_manager.list_cached_models() if self.model_manager else []
                cached_ids = [m.get("model_id") for m in cached] if cached else []
                
                if cached_ids:
                    display(HTML("<div class='apex-hint'>Cached Models</div>"))
                    html = "<ul>"
                    for m_id in cached_ids:
                        html += f"<li>{m_id}</li>"
                    html += "</ul>"
                    display(HTML(html))
                else:
                    display(HTML("<div>No models in cache.</div>"))

        def show_runtime(b=None):
            if not self.orchestrator:
                return
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "runtime" else ""
            
            with self.left_controls:
                self.left_controls.clear_output()
                display(HTML("<div class='apex-header'>Runtime API</div>"))
                
                api_status = "Online" if getattr(self, 'is_api_running', False) else "Offline"
                display(HTML(f"<div><b>API Server:</b> {api_status}</div>"))

        buttons["status"].on_click(show_status)
        buttons["workspace"].on_click(show_workspace)
        buttons["models"].on_click(show_models)
        buttons["runtime"].on_click(show_runtime)

        # Store the show_status method so we can call it after bind()
        self._refresh_status = show_status

        nav_vbox = widgets.VBox(list(buttons.values()))
        left_layout = widgets.VBox([nav_vbox, widgets.HTML("<hr>"), self.left_controls])
        left_layout.add_class('apex-left-panel')

        logger.info("APEX Runtime Console initialized.", extra={"prefix": "SYSTEM"})

        dashboard_layout = widgets.HBox([left_layout, right_console], layout=widgets.Layout(width='100%'))
        display(dashboard_layout)
        return dashboard_layout

    def refresh(self):
        """Refreshes the active UI tab (called after bind)."""
        if hasattr(self, '_refresh_status'):
            self._refresh_status()
