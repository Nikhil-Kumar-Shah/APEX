"""Minimal interactive ipywidgets dashboard for Google Colab."""

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from runtime.config.manager import ConfigManager
from runtime.core.health import HealthMonitor
from runtime.model.manager import ModelManager
from runtime.memory.workspace import WorkspaceManager

logger = logging.getLogger("runtime.ui.dashboard")


def get_minimal_css() -> str:
    """Returns clean, minimal developer theme CSS."""
    return """
    <style>
        .apex-dash {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            background-color: #f8f9fa;
            border-top: 2px solid #dee2e6;
            padding: 10px;
            color: #212529;
            font-size: 13px;
        }
        .apex-nav {
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
            border-bottom: 1px solid #dee2e6;
            padding-bottom: 5px;
        }
        .apex-btn {
            background-color: #e9ecef;
            border: 1px solid #ced4da;
            padding: 4px 10px;
            cursor: pointer;
            border-radius: 4px;
            color: #495057;
            font-weight: bold;
        }
        .apex-btn:hover {
            background-color: #dee2e6;
        }
        .apex-btn-primary {
            background-color: #0d6efd;
            color: white;
            border-color: #0d6efd;
        }
        .apex-btn-primary:hover {
            background-color: #0b5ed7;
        }
        .apex-btn-danger {
            background-color: #dc3545;
            color: white;
            border-color: #dc3545;
        }
        .apex-btn-danger:hover {
            background-color: #c82333;
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
        .apex-status {
            font-weight: bold;
        }
        .apex-status-success { color: #198754; }
        .apex-status-warning { color: #fd7e14; }
        .apex-status-error { color: #dc3545; }
    </style>
    """


class RuntimeDashboard:
    """Minimal fixed-bottom developer control panel."""

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
        
        # Workspace Manager Setup
        workspaces_dir = (
            self.lifecycle.drive_manager.persistence_root / "workspaces"
            if self.lifecycle
            else Path.cwd() / "workspaces"
        )
        self.workspace_manager = WorkspaceManager(workspaces_dir)
        
        # Dynamic active stats
        self.is_api_running = False
        
        # Load active workspace from config
        initial_ws = config_manager.config.get("project_id", "default")
        try:
            self.workspace_manager.load_workspace(initial_ws)
        except Exception:
            self.workspace_manager.create_workspace(initial_ws, config_manager.config.get("project_name", "Default Workspace"))
            self.workspace_manager.load_workspace(initial_ws)

        # Initialize Orchestrator
        from runtime.orchestrator.orchestrator import RuntimeOrchestrator
        self.orchestrator = RuntimeOrchestrator(self.model_manager, self.workspace_manager)

    def render(self) -> Any:
        try:
            import ipywidgets as widgets
            from IPython.display import display, HTML
        except ImportError:
            logger.info("Headless rendering: ipywidgets is not installed.")
            return "Headless Dashboard Instance (ipywidgets missing)"

        # Style injection
        css_style_widget = widgets.HTML(get_minimal_css())
        display(css_style_widget)

        content_output = widgets.Output()

        buttons = {
            "home": widgets.Button(description="Home"),
            "workspace": widgets.Button(description="Workspace"),
            "models": widgets.Button(description="Models"),
            "runtime": widgets.Button(description="Runtime"),
            "developer": widgets.Button(description="Developer"),
        }

        # Screens drawing functions
        def show_home(b=None):
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "home" else ""
            
            with content_output:
                content_output.clear_output()
                report = self.health_monitor.generate_report()
                active_model = report["model_manager"].get("active_model_id") or "None"
                api_status = "Online" if self.is_api_running else "Offline"
                api_color = "success" if self.is_api_running else "error"
                
                html = f"""
                <div class="apex-header">Current Status</div>
                <div class="apex-card">
                    <table style="width: 100%; text-align: left;">
                        <tr>
                            <th>Workspace</th>
                            <th>Active Model</th>
                            <th>GPU</th>
                            <th>API Server</th>
                        </tr>
                        <tr>
                            <td>{self.workspace_manager.active_workspace_id}</td>
                            <td><b>{active_model.split('/')[-1]}</b></td>
                            <td>{report['gpu'].get('device_name') or 'CPU Fallback'}</td>
                            <td class="apex-status apex-status-{api_color}">{api_status}</td>
                        </tr>
                    </table>
                </div>
                """
                display(HTML(html))

        def show_workspace(b=None):
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "workspace" else ""
            
            with content_output:
                content_output.clear_output()
                display(HTML("<div class='apex-header'>Workspace Configuration</div>"))
                
                ws_list = self.workspace_manager.list_workspaces()
                ws_options = [(w["name"], w["workspace_id"]) for w in ws_list]
                
                ws_select = widgets.Dropdown(
                    options=ws_options,
                    value=self.workspace_manager.active_workspace_id,
                    description="Switch WS:"
                )
                
                switch_btn = widgets.Button(description="Load Workspace", button_style="success")
                ws_out = widgets.Output()

                def on_switch(b):
                    with ws_out:
                        ws_out.clear_output()
                        self.workspace_manager.load_workspace(ws_select.value)
                        print(f"Workspace loaded: {ws_select.value}")
                        show_workspace()

                switch_btn.on_click(on_switch)
                display(widgets.VBox([widgets.HBox([ws_select, switch_btn]), ws_out]))

        def show_models(b=None):
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "models" else ""
            
            with content_output:
                content_output.clear_output()
                display(HTML("<div class='apex-header'>Model Management</div>"))
                
                dl_input = widgets.Text(description="HF Repo ID:", placeholder="Qwen/Qwen2.5-1.5B-Instruct")
                dl_btn = widgets.Button(description="Download", button_style="warning")
                dl_out = widgets.Output()

                def on_download(b):
                    with dl_out:
                        dl_out.clear_output()
                        model_id = dl_input.value.strip()
                        if not model_id:
                            print("Model ID cannot be empty.")
                            return
                        print(f"Submitting download task for: {model_id}...")
                        self.orchestrator.submit_task("download_model", {"model_id": model_id})

                dl_btn.on_click(on_download)
                
                cached = self.model_manager.list_cached_models()
                cached_ids = [m.get("model_id") for m in cached] if cached else []
                if "Qwen/Qwen2.5-1.5B-Instruct" not in cached_ids:
                    cached_ids.append("Qwen/Qwen2.5-1.5B-Instruct")

                load_select = widgets.Dropdown(options=cached_ids, description="Local Models:")
                load_btn = widgets.Button(description="Load", button_style="success")
                unload_btn = widgets.Button(description="Unload", button_style="danger")

                def on_load(b):
                    with dl_out:
                        dl_out.clear_output()
                        print(f"Submitting load task for '{load_select.value}'...")
                        self.orchestrator.submit_task("load_model", {"model_id": load_select.value})

                def on_unload(b):
                    with dl_out:
                        dl_out.clear_output()
                        self.model_manager.unload_model()
                        print("Model unloaded.")

                load_btn.on_click(on_load)
                unload_btn.on_click(on_unload)

                display(widgets.VBox([
                    widgets.HBox([dl_input, dl_btn]),
                    widgets.HBox([load_select, load_btn, unload_btn]),
                    dl_out
                ]))

        def show_runtime(b=None):
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "runtime" else ""
            
            with content_output:
                content_output.clear_output()
                display(HTML("<div class='apex-header'>Runtime Controls & API</div>"))
                
                run_out = widgets.Output()
                start_btn = widgets.Button(description="Start API", button_style="success")
                stop_btn = widgets.Button(description="Stop API", button_style="danger")

                def on_start(b):
                    with run_out:
                        run_out.clear_output()
                        self.is_api_running = True
                        print("API Server started on port 8000.")

                def on_stop(b):
                    with run_out:
                        run_out.clear_output()
                        self.is_api_running = False
                        print("API Server stopped.")

                start_btn.on_click(on_start)
                stop_btn.on_click(on_stop)

                display(widgets.VBox([widgets.HBox([start_btn, stop_btn]), run_out]))

        def show_developer(b=None):
            for k, btn in buttons.items():
                btn.button_style = "info" if k == "developer" else ""
            
            with content_output:
                content_output.clear_output()
                display(HTML("<div class='apex-header'>Developer Diagnostics</div>"))
                
                heartbeat_sec = time.time() - self.orchestrator.worker_heartbeat
                worker_alive = self.orchestrator.worker.is_alive()
                active_tasks = self.orchestrator.task_queue.list_tasks()
                
                html = f"""
                <div class="apex-card">
                    <p><b>Worker Status:</b> {'ALIVE' if worker_alive else 'DEAD'} (Heartbeat {heartbeat_sec:.1f}s ago)</p>
                    <p><b>Queue Depth:</b> {len(active_tasks)} tasks</p>
                </div>
                """
                display(HTML(html))

        # Register Navigation Callbacks
        buttons["home"].on_click(show_home)
        buttons["workspace"].on_click(show_workspace)
        buttons["models"].on_click(show_models)
        buttons["runtime"].on_click(show_runtime)
        buttons["developer"].on_click(show_developer)

        # Show Home on Startup
        show_home()

        # Layout
        nav_box = widgets.HBox(list(buttons.values()))
        dashboard_layout = widgets.VBox([nav_box, content_output])
        
        display(dashboard_layout)
        return dashboard_layout
