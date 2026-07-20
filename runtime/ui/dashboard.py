"""Minimal side-by-side interactive dashboard for Google Colab with integrated unified console."""

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
    </style>
    """


class RuntimeDashboard:
    """Side-by-side developer control panel (Left: Controls, Right: Terminal Output)."""

    def __init__(
        self,
        config_manager: ConfigManager,
        model_manager: ModelManager,
        health_monitor: HealthMonitor,
        log_filepath: Path,
        lifecycle: Optional[Any] = None,
    ):
        self.config_manager = config_manager
        self.model_manager = model_manager
        self.health_monitor = health_monitor
        self.lifecycle = lifecycle
        
        workspaces_dir = (
            self.lifecycle.drive_manager.persistence_root / "workspaces"
            if self.lifecycle else Path.cwd() / "workspaces"
        )
        self.workspace_manager = WorkspaceManager(workspaces_dir)
        self.is_api_running = False
        
        initial_ws = config_manager.config.get("project_id", "default")
        try:
            self.workspace_manager.load_workspace(initial_ws)
        except Exception:
            self.workspace_manager.create_workspace(initial_ws, config_manager.config.get("project_name", "Default Workspace"))
            self.workspace_manager.load_workspace(initial_ws)

        from runtime.orchestrator.orchestrator import RuntimeOrchestrator
        self.orchestrator = RuntimeOrchestrator(self.model_manager, self.workspace_manager)

    def render(self) -> Any:
        try:
            import ipywidgets as widgets
            from IPython.display import display, HTML
        except ImportError:
            logger.info("Headless rendering: ipywidgets is not installed.", extra={"prefix": "SYSTEM"})
            return "Headless Dashboard Instance"

        display(widgets.HTML(get_minimal_css()))

        # Layout containers
        left_controls = widgets.Output()
        left_controls.add_class('apex-left-panel')
        
        right_console = widgets.Output()
        right_console.add_class('apex-right-panel')

        # Bind the global logger to this right_console widget
        widget_handler = get_widget_handler()
        widget_handler.set_widget(right_console)

        # Navigation Buttons (Vertical)
        buttons = {
            "status": widgets.Button(description="Status", layout=widgets.Layout(width='100%')),
            "workspace": widgets.Button(description="Workspace", layout=widgets.Layout(width='100%')),
            "models": widgets.Button(description="Models", layout=widgets.Layout(width='100%')),
            "runtime": widgets.Button(description="Runtime API", layout=widgets.Layout(width='100%')),
        }

        def show_status(b=None):
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "status" else ""
            
            with left_controls:
                left_controls.clear_output()
                report = self.health_monitor.generate_report()
                active_model = report["model_manager"].get("active_model_id") or "None"
                api_status = "Online" if self.is_api_running else "Offline"
                worker_alive = self.orchestrator.worker.is_alive()
                active_tasks = self.orchestrator.task_queue.list_tasks()
                
                html = f"""
                <div class="apex-header">Status</div>
                <div class="apex-card">
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
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "workspace" else ""
            
            with left_controls:
                left_controls.clear_output()
                display(HTML("<div class='apex-header'>Workspace</div>"))
                
                ws_list = self.workspace_manager.list_workspaces()
                ws_options = [(w["name"], w["workspace_id"]) for w in ws_list]
                ws_select = widgets.Dropdown(options=ws_options, value=self.workspace_manager.active_workspace_id, layout=widgets.Layout(width='90%'))
                switch_btn = widgets.Button(description="Load Workspace", button_style="success", layout=widgets.Layout(width='90%'))

                def on_switch(b):
                    self.workspace_manager.load_workspace(ws_select.value)
                    logger.info(f"Loaded '{ws_select.value}'", extra={"prefix": "SUCCESS"})
                    show_status()

                switch_btn.on_click(on_switch)
                display(widgets.VBox([ws_select, switch_btn]))

        def show_models(b=None):
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "models" else ""
            
            with left_controls:
                left_controls.clear_output()
                display(HTML("<div class='apex-header'>Model Controls</div>"))
                
                dl_input = widgets.Text(placeholder="HF Repo ID", layout=widgets.Layout(width='90%'))
                dl_btn = widgets.Button(description="Download", button_style="warning", layout=widgets.Layout(width='90%'))

                def on_download(b):
                    model_id = dl_input.value.strip()
                    if model_id:
                        logger.info(f"Submitting download task for: {model_id}...", extra={"prefix": "MODEL"})
                        self.orchestrator.submit_task("download_model", {"model_id": model_id})

                dl_btn.on_click(on_download)
                
                cached = self.model_manager.list_cached_models()
                cached_ids = [m.get("model_id") for m in cached] if cached else ["Qwen/Qwen2.5-1.5B-Instruct"]
                load_select = widgets.Dropdown(options=cached_ids, layout=widgets.Layout(width='90%'))
                load_btn = widgets.Button(description="Load Model", button_style="success", layout=widgets.Layout(width='90%'))
                unload_btn = widgets.Button(description="Unload", button_style="danger", layout=widgets.Layout(width='90%'))

                def on_load(b):
                    logger.info(f"Submitting load task for '{load_select.value}'...", extra={"prefix": "MODEL"})
                    self.orchestrator.submit_task("load_model", {"model_id": load_select.value})

                def on_unload(b):
                    self.model_manager.unload_model()
                    logger.info("Unloaded model from memory.", extra={"prefix": "SUCCESS"})

                load_btn.on_click(on_load)
                unload_btn.on_click(on_unload)

                display(widgets.VBox([dl_input, dl_btn, widgets.HTML("<hr>"), load_select, load_btn, unload_btn]))

        def show_runtime(b=None):
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "runtime" else ""
            
            with left_controls:
                left_controls.clear_output()
                display(HTML("<div class='apex-header'>API Server</div>"))
                
                start_btn = widgets.Button(description="Start API", button_style="success", layout=widgets.Layout(width='90%'))
                stop_btn = widgets.Button(description="Stop API", button_style="danger", layout=widgets.Layout(width='90%'))

                def on_start(b):
                    self.is_api_running = True
                    logger.info("API Server started on port 8000.", extra={"prefix": "API"})

                def on_stop(b):
                    self.is_api_running = False
                    logger.info("API Server stopped.", extra={"prefix": "API"})

                start_btn.on_click(on_start)
                stop_btn.on_click(on_stop)

                display(widgets.VBox([start_btn, stop_btn]))

        buttons["status"].on_click(show_status)
        buttons["workspace"].on_click(show_workspace)
        buttons["models"].on_click(show_models)
        buttons["runtime"].on_click(show_runtime)

        show_status()

        nav_vbox = widgets.VBox(list(buttons.values()))
        left_layout = widgets.VBox([nav_vbox, widgets.HTML("<hr>"), left_controls])
        left_layout.add_class('apex-left-panel')

        logger.info("APEX UI Initialized.", extra={"prefix": "SYSTEM"})
        logger.info("Console output will stream here.", extra={"prefix": "SYSTEM"})

        dashboard_layout = widgets.HBox([left_layout, right_console], layout=widgets.Layout(width='100%'))
        display(dashboard_layout)
        return dashboard_layout
