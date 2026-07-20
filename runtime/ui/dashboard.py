"""Minimal read-only status monitor dashboard for Google Colab — APEX V1."""

import logging
from typing import Any, Optional

from runtime.config.manager import ConfigManager
from runtime.core.health import HealthMonitor
from runtime.model.manager import ModelManager
from runtime.memory.workspace import WorkspaceManager
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
            width: 30%;
            border-right: 2px solid #dee2e6;
            padding-right: 15px;
            margin-right: 15px;
        }
        .apex-right-panel {
            width: 70%;
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 10px;
            border-radius: 4px;
            font-family: "Courier New", monospace;
            height: 400px;
            overflow-y: auto;
        }
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
    </style>
    """


class RuntimeDashboard:
    """Read-only developer control panel (Left: Status, Right: Terminal Console)."""

    def __init__(self):
        self.config_manager: Optional[ConfigManager] = None
        self.model_manager: Optional[ModelManager] = None
        self.health_monitor: Optional[HealthMonitor] = None
        self.lifecycle: Optional[Any] = None
        self.workspace_manager: Optional[WorkspaceManager] = None
        self.orchestrator: Optional[Any] = None
        self.is_api_running = False
        
        self.status_output: Optional[Any] = None

    def bind_managers(
        self,
        config_manager: ConfigManager,
        model_manager: ModelManager,
        health_monitor: HealthMonitor,
        lifecycle: Any,
        orchestrator: Any = None
    ):
        """Binds backend managers to observe their states."""
        self.config_manager = config_manager
        self.model_manager = model_manager
        self.health_monitor = health_monitor
        self.lifecycle = lifecycle
        self.orchestrator = orchestrator
        
        workspaces_dir = self.lifecycle.drive_manager.persistence_root / "workspaces"
        self.workspace_manager = WorkspaceManager(workspaces_dir)

    def render(self) -> Any:
        """Renders the single status pane and the logging terminal widget."""
        try:
            import ipywidgets as widgets
            from IPython.display import display, HTML
        except ImportError:
            logger.info("Headless rendering: ipywidgets is not installed.", extra={"prefix": "SYSTEM"})
            return "Headless Dashboard Instance"

        display(widgets.HTML(get_minimal_css()))

        self.status_output = widgets.Output()
        self.status_output.add_class('apex-left-panel')
        
        right_console = widgets.Output()
        right_console.add_class('apex-right-panel')

        widget_handler = get_widget_handler()
        widget_handler.set_widget(right_console)

        logger.info("APEX Runtime Console initialized.", extra={"prefix": "SYSTEM"})

        dashboard_layout = widgets.HBox([self.status_output, right_console], layout=widgets.Layout(width='100%'))
        display(dashboard_layout)
        return dashboard_layout

    def refresh(self):
        """Forces the status pane to redraw based on live backend metrics."""
        if not self.status_output or not self.health_monitor:
            return
            
        try:
            import ipywidgets as widgets
            from IPython.display import display, HTML
        except ImportError:
            return
            
        with self.status_output:
            self.status_output.clear_output()
            
            from runtime.api.state import RuntimeState
            # Try to grab state if API Manager exists, else fallback
            state_obj = None
            if hasattr(self, 'api_manager') and self.api_manager:
                state_obj = self.api_manager.state

            report = self.health_monitor.generate_report()
            active_model = report["model_manager"].get("active_model_id") or "None"
            
            # Use RuntimeState if available, otherwise fallback
            if state_obj:
                api_status = "Online" if state_obj.api_running else "Offline"
                auth = state_obj.authentication
                api_key = "**************" if state_obj.api_key else "None"
                tunnel = "Connected" if state_obj.tunnel_connected else "Disconnected"
                public_url = state_obj.public_url or "Hidden"
                queue_len = state_obj.queue_size
                reqs = state_obj.total_requests
            else:
                api_status = "Offline"
                auth = "Disabled"
                api_key = "None"
                tunnel = "Disconnected"
                public_url = "Hidden"
                queue_len = 0
                reqs = 0
            
            state_str = "UNKNOWN"
            if self.orchestrator:
                state_str = self.orchestrator.state_machine.current_state
                
            active_ws = self.workspace_manager.active_workspace_id if self.workspace_manager else "default"
            gpu_name = report['gpu'].get('device_name') or 'CPU Fallback'
            
            html = f"""
            <div class="apex-header">Live Status</div>
            <div class="apex-card">
                <b>State:</b> {state_str}<br>
                <b>Workspace:</b> {active_ws}<br>
                <b>Model:</b> {active_model.split('/')[-1]}<br>
                <b>GPU:</b> {gpu_name}<br>
                <hr>
                <b>API:</b> {api_status}<br>
                <b>Auth:</b> {auth}<br>
                <b>Key:</b> {api_key}<br>
                <b>Tunnel:</b> {tunnel} ({public_url})<br>
                <b>Queue:</b> {queue_len} pending<br>
                <b>Requests:</b> {reqs}
            </div>
            """
            display(HTML(html))
