"""Simplified, developer-grade status dashboard for APEX."""

import logging
from typing import Any, Optional

from runtime.config.manager import ConfigManager
from runtime.core.health import HealthMonitor
from runtime.logging.logger import get_widget_handler
from runtime.memory.workspace import WorkspaceManager
from runtime.model.manager import ModelManager

logger = logging.getLogger("runtime.ui.dashboard")


def get_dashboard_css() -> str:
    """Returns clean, developer-grade CSS for the runtime dashboard."""
    return """
    <style>
        .apex-dash-container {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 18px;
            max-width: 900px;
            margin: 10px 0;
            box-sizing: border-box;
        }
        .apex-dash-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #30363d;
            padding-bottom: 12px;
            margin-bottom: 14px;
        }
        .apex-dash-title {
            font-size: 16px;
            font-weight: 700;
            color: #58a6ff;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .apex-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 12px;
            margin-bottom: 14px;
        }
        .apex-tile {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 12px;
        }
        .apex-tile-label {
            font-size: 11px;
            font-weight: 600;
            color: #8b949e;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        .apex-tile-value {
            font-size: 14px;
            font-weight: 600;
            color: #f0f6fc;
            word-break: break-all;
        }
        .apex-access-box {
            background: #161b22;
            border: 1px solid #238636;
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 14px;
        }
        .apex-code-block {
            background: #090d13;
            border: 1px solid #21262d;
            border-radius: 6px;
            padding: 10px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 11px;
            color: #79c0ff;
            white-space: pre-wrap;
            word-break: break-all;
            margin-top: 8px;
        }
    </style>
    """


class RuntimeDashboard:
    """Developer-grade runtime status dashboard and control panel."""

    def __init__(self):
        self.config_manager: Optional[ConfigManager] = None
        self.model_manager: Optional[ModelManager] = None
        self.health_monitor: Optional[HealthMonitor] = None
        self.lifecycle: Optional[Any] = None
        self.workspace_manager: Optional[WorkspaceManager] = None
        self.orchestrator: Optional[Any] = None
        self.api_manager: Optional[Any] = None
        self.is_api_running = False

        self.status_output: Optional[Any] = None
        self.controls_box: Optional[Any] = None
        self.console_widget: Optional[Any] = None
        self.root_widget: Optional[Any] = None

    def bind_managers(
        self,
        config_manager: ConfigManager,
        model_manager: ModelManager,
        health_monitor: HealthMonitor,
        lifecycle: Any,
        orchestrator: Any = None,
    ):
        """Binds backend managers to observe their states."""
        self.config_manager = config_manager
        self.model_manager = model_manager
        self.health_monitor = health_monitor
        self.lifecycle = lifecycle
        self.orchestrator = orchestrator

        if hasattr(self.lifecycle, "drive_manager") and self.lifecycle.drive_manager:
            workspaces_dir = self.lifecycle.drive_manager.persistence_root / "workspaces"
            self.workspace_manager = WorkspaceManager(workspaces_dir)

    def render(self) -> Any:
        """Renders the dashboard with status tiles, access URL cards, and collapsible logs."""
        try:
            import ipywidgets as widgets
            from IPython.display import HTML, display
        except ImportError:
            logger.info("Headless rendering: ipywidgets is not installed.", extra={"prefix": "SYSTEM"})
            return "Headless Dashboard Instance"

        display(HTML(get_dashboard_css()))

        self.status_output = widgets.Output()

        # Action controls
        stop_btn = widgets.Button(
            description="Stop Server",
            button_style="danger",
            icon="stop",
            layout=widgets.Layout(width="130px"),
        )
        refresh_btn = widgets.Button(
            description="Refresh",
            button_style="",
            icon="refresh",
            layout=widgets.Layout(width="100px"),
        )

        def _on_stop_click(_):
            stop_btn.disabled = True
            stop_btn.description = "Stopping..."
            if self.api_manager:
                self.api_manager.stop()
            if self.orchestrator:
                self.orchestrator.state_machine.transition_to("STOPPED")
            self.refresh()
            stop_btn.disabled = False
            stop_btn.description = "Stop Server"

        def _on_refresh_click(_):
            self.refresh()

        stop_btn.on_click(_on_stop_click)
        refresh_btn.on_click(_on_refresh_click)

        self.controls_box = widgets.HBox(
            [refresh_btn, stop_btn],
            layout=widgets.Layout(gap="10px", margin="8px 0"),
        )

        # Technical console in collapsible accordion
        self.console_widget = widgets.Output()
        self.console_widget.layout = widgets.Layout(
            background_color="#090d13",
            color="#c9d1d9",
            height="260px",
            overflow_y="auto",
            padding="8px",
        )

        widget_handler = get_widget_handler()
        widget_handler.set_widget(self.console_widget)

        accordion = widgets.Accordion(children=[self.console_widget])
        accordion.set_title(0, "📋 Live Runtime Console & Diagnostic Logs")
        accordion.selected_index = None  # Collapsed by default

        self.root_widget = widgets.VBox(
            [self.status_output, self.controls_box, accordion],
            layout=widgets.Layout(
                background_color="#0d1117",
                border="1px solid #30363d",
                border_radius="10px",
                padding="16px",
                max_width="850px",
            ),
        )

        display(self.root_widget)
        self.refresh()
        return self.root_widget

    def refresh(self):
        """Forces the status cards to redraw based on live backend metrics."""
        if not self.status_output:
            return

        try:
            import ipywidgets as widgets
            from IPython.display import HTML
        except ImportError:
            return

        with self.status_output:
            self.status_output.clear_output()

            state_obj = self.api_manager.state if hasattr(self, "api_manager") and self.api_manager else None

            # Gather telemetry
            report = self.health_monitor.generate_report() if self.health_monitor else {"model_manager": {}, "gpu": {}}
            active_model = report.get("model_manager", {}).get("active_model_id") or "None"

            gpu_name = report.get("gpu", {}).get("device_name") or "CPU Fallback"

            if state_obj:
                api_status = state_obj.api_status.value
                public_url = state_obj.public_url or "—"
                openai_url = state_obj.openai_url or "—"
                queue_len = state_obj.queue_size
                reqs = state_obj.total_requests
                health_ms = f"{state_obj.last_health_ms:.0f} ms" if state_obj.last_health_ms else "—"
                last_error = state_obj.last_error or "None"
            else:
                api_status = "STOPPED"
                public_url = "—"
                openai_url = "—"
                queue_len = 0
                reqs = 0
                health_ms = "—"
                last_error = "None"

            runtime_state = "IDLE"
            if self.orchestrator:
                runtime_state = self.orchestrator.state_machine.current_state

            # Colors
            status_colors = {
                "STOPPED": "#8b949e",
                "STARTING": "#d29922",
                "VERIFYING": "#58a6ff",
                "RUNNING": "#3fb950",
                "FAILED": "#f85149",
            }
            status_color = status_colors.get(api_status, "#8b949e")

            # Access box markup when running
            access_html = ""
            if api_status == "RUNNING" and public_url != "—":
                curl_cmd = f"""curl -X POST {openai_url}/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{{\"model\": \"{active_model}\", \"messages\": [{{\"role\": \"user\", \"content\": \"Hello!\"}}]}}'"""
                access_html = f"""
                <div class="apex-access-box">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 700; color: #3fb950; font-size: 14px;">● Public Endpoint Online</span>
                        <span style="background: #23863626; color: #3fb950; border: 1px solid #2ea0434d; padding: 2px 8px; border-radius: 10px; font-size: 11px;">Verified</span>
                    </div>
                    <div style="margin-top: 8px; font-size: 13px;">
                        <div><b>OpenAI Base URL:</b> <a href="{openai_url}" target="_blank" style="color: #58a6ff; font-weight: 600;">{openai_url}</a></div>
                        <div style="margin-top: 4px;"><b>Public Tunnel:</b> <a href="{public_url}" target="_blank" style="color: #8b949e;">{public_url}</a></div>
                    </div>
                    <div style="margin-top: 8px; font-size: 11px; color: #8b949e; font-weight: 600;">Test cURL:</div>
                    <div class="apex-code-block">{curl_cmd}</div>
                </div>
                """

            html = f"""
            <div class="apex-dash-container">
                <div class="apex-dash-header">
                    <div class="apex-dash-title">🌌 APEX Runtime Dashboard</div>
                    <div><span style="background: {status_color}26; color: {status_color}; border: 1px solid {status_color}4d; padding: 3px 10px; border-radius: 12px; font-weight: 700; font-size: 12px;">{api_status}</span></div>
                </div>

                {access_html}

                <div class="apex-grid">
                    <div class="apex-tile">
                        <div class="apex-tile-label">Lifecycle State</div>
                        <div class="apex-tile-value">{runtime_state}</div>
                    </div>
                    <div class="apex-tile">
                        <div class="apex-tile-label">Active Model</div>
                        <div class="apex-tile-value">{active_model}</div>
                    </div>
                    <div class="apex-tile">
                        <div class="apex-tile-label">Hardware Device</div>
                        <div class="apex-tile-value">{gpu_name}</div>
                    </div>
                    <div class="apex-tile">
                        <div class="apex-tile-label">Health Latency</div>
                        <div class="apex-tile-value">{health_ms}</div>
                    </div>
                    <div class="apex-tile">
                        <div class="apex-tile-label">Requests Served</div>
                        <div class="apex-tile-value">{reqs} (queue: {queue_len})</div>
                    </div>
                    <div class="apex-tile">
                        <div class="apex-tile-label">Last Error</div>
                        <div class="apex-tile-value" style="color: {'#f85149' if last_error != 'None' else '#8b949e'}">{last_error}</div>
                    </div>
                </div>
            </div>
            """
            from IPython.display import HTML
            from IPython.display import display as ipy_display
            ipy_display(HTML(html))
