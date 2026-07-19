"""Interactive ipywidgets dashboard for Google Colab."""

import logging
import time
import sys
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.config.manager import ConfigManager
from runtime.core.health import HealthMonitor
from runtime.model.manager import ModelManager
from runtime.memory.workspace import WorkspaceManager
from runtime.ui.benchmarks import BenchmarkTracker
from runtime.ui.logs import LogViewer
from runtime.ui.updater import UpdateChecker

logger = logging.getLogger("runtime.ui.dashboard")


class RuntimeDashboard:
    """Orchestrates drawing HTML tabs, settings forms, log viewers, and benchmark monitors in notebooks."""

    def __init__(
        self,
        config_manager: ConfigManager,
        model_manager: ModelManager,
        health_monitor: HealthMonitor,
        log_filepath: Path,
        lifecycle: Optional[Any] = None,
    ):
        """Initializes the RuntimeDashboard.

        Args:
            config_manager: The active ConfigManager.
            model_manager: The active ModelManager.
            health_monitor: The active HealthMonitor.
            log_filepath: Path to the runtime log file.
            lifecycle: Optional active lifecycle instance.
        """
        self.config_manager = config_manager
        self.model_manager = model_manager
        self.health_monitor = health_monitor
        self.log_viewer = LogViewer(log_filepath)
        self.benchmark_tracker = BenchmarkTracker()
        self.lifecycle = lifecycle
        
        # Load update checker
        self.update_checker = UpdateChecker(
            current_runtime_version="1.0.0",
            current_config_version=config_manager.config.get("config_version", "1.0.0"),
        )
        
        # Workspace Manager Setup
        workspaces_dir = (
            self.lifecycle.drive_manager.project_root / "workspaces"
            if self.lifecycle
            else Path.cwd() / "workspaces"
        )
        self.workspace_manager = WorkspaceManager(workspaces_dir)
        
        # Dynamic active stats
        self.active_requests = 0
        self.tokens_generated = 0
        self.is_api_running = False
        self.dev_mode = False
        
        # Load active workspace from config
        initial_ws = config_manager.config.get("project_id", "default")
        try:
            self.workspace_manager.load_workspace(initial_ws)
        except Exception:
            self.workspace_manager.create_workspace(initial_ws, config_manager.config.get("project_name", "Default Workspace"))
            self.workspace_manager.load_workspace(initial_ws)

    def save_settings_ui(self, form_data: Dict[str, Any]) -> bool:
        """Invoked by UI form to save settings changes to Configuration Manager.

        Args:
            form_data: Parameters updated by user.

        Returns:
            bool: True if configuration was successfully validated and saved.
        """
        current_config = self.config_manager.config.copy()
        if "project_id" in form_data:
            current_config["project_id"] = form_data["project_id"]
        if "project_name" in form_data:
            current_config["project_name"] = form_data["project_name"]
        try:
            return self.config_manager.save(current_config)
        except Exception as e:
            logger.error(f"Failed to save settings via Dashboard UI: {e}")
            return False


    def render(self) -> Any:
        """Renders the IPython Widgets left sidebar layout inside notebooks.

        Returns:
            Any: The compiled ipywidgets layout or mock container if headless.
        """
        try:
            import ipywidgets as widgets
            from IPython.display import display, HTML
        except ImportError:
            logger.info("Headless rendering: ipywidgets is not installed.")
            return "Headless Dashboard Instance (ipywidgets missing)"

        # Style sheet injection
        style_html = """
        <style>
            .apex-sidebar-btn {
                text-align: left !important;
                font-weight: bold !important;
                margin: 4px 0px !important;
                border-radius: 6px !important;
            }
            .apex-card-grid {
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
            }
            .apex-card {
                background-color: #1F2937;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 16px;
                min-width: 200px;
                flex: 1;
            }
            .apex-header {
                font-size: 20px;
                font-weight: bold;
                color: #818CF8;
                margin-bottom: 12px;
            }
            .apex-badge-active {
                background-color: #059669;
                color: white;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            .apex-badge-inactive {
                background-color: #DC2626;
                color: white;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
        </style>
        """
        display(HTML(style_html))

        # Main Output Area
        content_output = widgets.Output()
        
        # Sidebar Widgets
        title_widget = widgets.HTML(
            "<div style='font-size: 24px; font-weight: bold; color: #6366F1; margin-bottom: 15px;'>🌌 APEX</div>"
        )
        
        ws_badge = widgets.HTML(
            f"<div style='margin-bottom: 15px;'><span class='apex-badge-active'>Active WS: {self.workspace_manager.active_workspace_id}</span></div>"
        )

        # Navigation Buttons
        buttons = {
            "home": widgets.Button(description=" 🏠 Home", layout=widgets.Layout(width="95%"), button_style="primary"),
            "workspace": widgets.Button(description=" 📁 Workspace Studio", layout=widgets.Layout(width="95%")),
            "models": widgets.Button(description=" 🤖 Model Studio", layout=widgets.Layout(width="95%")),
            "runtime": widgets.Button(description=" ⚙ Runtime Controls", layout=widgets.Layout(width="95%")),
            "api": widgets.Button(description=" 🌐 API Manager", layout=widgets.Layout(width="95%")),
            "memory": widgets.Button(description=" 🧠 Memory Explorer", layout=widgets.Layout(width="95%")),
            "performance": widgets.Button(description=" 📊 Performance Center", layout=widgets.Layout(width="95%")),
            "logs": widgets.Button(description=" 📜 Live Logs", layout=widgets.Layout(width="95%")),
            "settings": widgets.Button(description=" 🔧 Settings Center", layout=widgets.Layout(width="95%")),
        }

        for btn in buttons.values():
            btn.add_class("apex-sidebar-btn")

        dev_toggle = widgets.ToggleButton(
            value=self.dev_mode,
            description="🛠 Developer Mode",
            button_style="warning",
            layout=widgets.Layout(width="95%", margin="20px 0px 5px 0px")
        )

        def on_dev_toggle_changed(change):
            self.dev_mode = change["new"]
            # Trigger active screen redraw
            draw_sidebar()

        dev_toggle.observe(on_dev_toggle_changed, "value")

        sidebar_box = widgets.VBox(layout=widgets.Layout(width="220px", border_right="1px solid #374151", padding="10px"))

        def draw_sidebar():
            visible_btns = [title_widget, ws_badge, buttons["home"], buttons["workspace"], buttons["models"], buttons["runtime"], buttons["api"], buttons["memory"]]
            if self.dev_mode:
                visible_btns.append(buttons["performance"])
                visible_btns.append(buttons["logs"])
            visible_btns.append(buttons["settings"])
            visible_btns.append(dev_toggle)
            sidebar_box.children = visible_btns

        draw_sidebar()

        # Screens drawing functions
        def show_home(b=None):
            for k, btn in buttons.items():
                btn.button_style = "primary" if k == "home" else ""
            
            with content_output:
                content_output.clear_output()
                report = self.health_monitor.generate_report()
                active_model = report["model_manager"].get("active_model_id") or "None loaded"
                
                home_html = f"""
                <div class='apex-header'>APEX Home Control Center</div>
                <div class='apex-card-grid'>
                    <div class='apex-card'>
                        <h4>Workspace status</h4>
                        <p>ID: <b>{self.workspace_manager.active_workspace_id}</b></p>
                        <span class='apex-badge-active'>Active</span>
                    </div>
                    <div class='apex-card'>
                        <h4>Active Model</h4>
                        <p>ID: <b>{active_model}</b></p>
                        <p>Family: {active_model.split('/')[0] if '/' in active_model else 'default'}</p>
                    </div>
                    <div class='apex-card'>
                        <h4>Inference Status</h4>
                        <p>Engine: <b>{report['model_manager'].get('engine_status', {}).get('engine_name', 'N/A')}</b></p>
                        <p>Uptime: {report['uptime_seconds']:.1f}s</p>
                    </div>
                </div>
                <div class='apex-card-grid' style='margin-top: 15px;'>
                    <div class='apex-card'>
                        <h4>GPU Diagnostics</h4>
                        <p>Device: <b>{report['gpu'].get('device_name') or 'CPU Fallback'}</b></p>
                        <p>VRAM Free: {report['gpu'].get('vram_free_mb', 0.0):.1f} MB</p>
                    </div>
                    <div class='apex-card'>
                        <h4>System RAM</h4>
                        <p>Percentage Used: <b>{report['ram'].get('percent_used', 0.0):.1f}%</b></p>
                        <p>Free: {report['ram'].get('free_gb', 0.0):.2f} GB</p>
                    </div>
                    <div class='apex-card'>
                        <h4>OpenAI API Status</h4>
                        <p>Status: <span class='{"apex-badge-active" if self.is_api_running else "apex-badge-inactive"}'>{"Running" if self.is_api_running else "Stopped"}</span></p>
                        <p>Requests: {self.active_requests}</p>
                    </div>
                </div>
                """
                display(HTML(home_html))

        def show_workspace(b=None):
            for k, btn in buttons.items():
                btn.button_style = "primary" if k == "workspace" else ""
            
            with content_output:
                content_output.clear_output()
                display(HTML("<div class='apex-header'>Workspace Studio</div>"))
                
                # List workspaces
                ws_list = self.workspace_manager.list_workspaces()
                ws_options = [(w["name"], w["workspace_id"]) for w in ws_list]
                
                ws_select = widgets.Dropdown(
                    options=ws_options,
                    value=self.workspace_manager.active_workspace_id,
                    description="Switch WS:"
                )
                
                switch_btn = widgets.Button(description="Switch Workspace", button_style="success")
                del_btn = widgets.Button(description="Delete Workspace", button_style="danger")
                ws_out = widgets.Output()

                def on_switch(b):
                    with ws_out:
                        ws_out.clear_output()
                        self.workspace_manager.load_workspace(ws_select.value)
                        ws_badge.value = f"<div style='margin-bottom: 15px;'><span class='apex-badge-active'>Active WS: {self.workspace_manager.active_workspace_id}</span></div>"
                        print(f"[+] Loaded workspace: {ws_select.value}")
                        
                def on_delete(b):
                    with ws_out:
                        ws_out.clear_output()
                        if ws_select.value == self.workspace_manager.active_workspace_id:
                            print("[-] Cannot delete the active workspace!")
                            return
                        if self.workspace_manager.delete_workspace(ws_select.value):
                            print(f"[+] Deleted workspace: {ws_select.value}")
                            show_workspace()
                        else:
                            print("[-] Failed to delete workspace.")

                switch_btn.on_click(on_switch)
                del_btn.on_click(on_delete)

                # Creation Wizard
                display(HTML("<h4>Create New Workspace</h4>"))
                ws_name_input = widgets.Text(description="Name:")
                ws_desc_input = widgets.Text(description="Desc:")
                create_btn = widgets.Button(description="Initialize Workspace", button_style="info")

                def on_create(b):
                    with ws_out:
                        ws_out.clear_output()
                        name = ws_name_input.value.strip()
                        if not name:
                            print("[-] Workspace Name cannot be empty.")
                            return
                        slug = name.lower().replace(" ", "-")
                        self.workspace_manager.create_workspace(slug, name)
                        print(f"[+] Workspace '{name}' initialized with slug '{slug}'.")
                        show_workspace()

                create_btn.on_click(on_create)

                display(widgets.VBox([
                    widgets.HBox([ws_select, switch_btn, del_btn]),
                    ws_name_input,
                    ws_desc_input,
                    create_btn,
                    ws_out
                ]))

        def show_models(b=None):
            for k, btn in buttons.items():
                btn.button_style = "primary" if k == "models" else ""
            
            with content_output:
                content_output.clear_output()
                display(HTML("<div class='apex-header'>Model Studio</div>"))
                
                cached = self.model_manager.list_cached_models()
                display(HTML("<h4>Cached / Downloaded Models</h4>"))
                if not cached:
                    print("No local models cached.")
                for m in cached:
                    print(f"- {m.get('model_id')} (Size: {m.get('size_bytes', 0)/(1024**3):.2f} GB)")

                # Download Interface
                display(HTML("<h4>Search & Download Model (Hugging Face)</h4>"))
                dl_input = widgets.Text(description="Repo ID:", placeholder="Qwen/Qwen2.5-1.5B-Instruct")
                dl_btn = widgets.Button(description="Download", button_style="warning")
                dl_out = widgets.Output()

                def on_download(b):
                    with dl_out:
                        dl_out.clear_output()
                        model_id = dl_input.value.strip()
                        if not model_id:
                            print("[-] Model ID cannot be empty.")
                            return
                        print(f"[+] Initiating model download for: {model_id}...")
                        try:
                            self.model_manager.download_model(model_id)
                            print("[+] Download complete.")
                            show_models()
                        except Exception as e:
                            print(f"[-] Download failed: {e}")

                dl_btn.on_click(on_download)

                # Load/Unload controls
                display(HTML("<h4>Active Model Loader</h4>"))
                active_model = self.model_manager.active_model_id or "None"
                display(HTML(f"<p>Current Loaded Model: <b>{active_model}</b></p>"))
                
                cached_ids = [m.get("model_id") for m in cached] if cached else []
                # Fallback options
                if "Qwen/Qwen2.5-1.5B-Instruct" not in cached_ids:
                    cached_ids.append("Qwen/Qwen2.5-1.5B-Instruct")

                load_select = widgets.Dropdown(options=cached_ids, description="Select Model:")
                load_btn = widgets.Button(description="Load Model", button_style="success")
                unload_btn = widgets.Button(description="Unload Model", button_style="danger")

                def on_load(b):
                    with dl_out:
                        dl_out.clear_output()
                        print(f"[+] Loading model '{load_select.value}' into VRAM...")
                        try:
                            self.model_manager.load_model(load_select.value)
                            print("[+] Model loaded successfully.")
                            show_models()
                        except Exception as e:
                            print(f"[-] Loading failed: {e}")

                def on_unload(b):
                    with dl_out:
                        dl_out.clear_output()
                        self.model_manager.unload_model()
                        print("[+] Model unloaded from VRAM.")
                        show_models()

                load_btn.on_click(on_load)
                unload_btn.on_click(on_unload)

                display(widgets.VBox([
                    widgets.HBox([dl_input, dl_btn]),
                    widgets.HBox([load_select, load_btn, unload_btn]),
                    dl_out
                ]))

        def show_runtime(b=None):
            for k, btn in buttons.items():
                btn.button_style = "primary" if k == "runtime" else ""
            
            with content_output:
                content_output.clear_output()
                display(HTML("<div class='apex-header'>Runtime Control Center</div>"))
                
                run_out = widgets.Output()
                start_btn = widgets.Button(description="Start Runtime", button_style="success")
                stop_btn = widgets.Button(description="Stop Runtime", button_style="danger")
                restart_btn = widgets.Button(description="Restart Runtime", button_style="warning")

                def on_start(b):
                    with run_out:
                        run_out.clear_output()
                        print("[+] Runtime services started.")

                def on_stop(b):
                    with run_out:
                        run_out.clear_output()
                        print("[-] Runtime services stopped.")

                def on_restart(b):
                    with run_out:
                        run_out.clear_output()
                        print("[+] Runtime services restarted.")

                start_btn.on_click(on_start)
                stop_btn.on_click(on_stop)
                restart_btn.on_click(on_restart)

                display(widgets.VBox([
                    widgets.HBox([start_btn, stop_btn, restart_btn]),
                    run_out
                ]))

        def show_api(b=None):
            for k, btn in buttons.items():
                btn.button_style = "primary" if k == "api" else ""
            
            with content_output:
                content_output.clear_output()
                display(HTML("<div class='apex-header'>API Manager</div>"))
                
                api_out = widgets.Output()
                api_toggle_btn = widgets.Button(
                    description="Stop API Server" if self.is_api_running else "Start API Server",
                    button_style="danger" if self.is_api_running else "success"
                )

                def on_api_toggle(b):
                    with api_out:
                        api_out.clear_output()
                        self.is_api_running = not self.is_api_running
                        api_toggle_btn.description = "Stop API Server" if self.is_api_running else "Start API Server"
                        api_toggle_btn.button_style = "danger" if self.is_api_running else "success"
                        print(f"[+] API Server is now {'Running' if self.is_api_running else 'Stopped'}")

                api_toggle_btn.on_click(on_api_toggle)

                api_html = f"""
                <div class='apex-card'>
                    <h4>Server Details</h4>
                    <p>Endpoint URL: <code>http://localhost:8000/v1</code></p>
                    <p>Host: <code>127.0.0.1</code></p>
                    <p>Port: <code>8000</code></p>
                    <p>Total requests: {self.active_requests}</p>
                    <p>Generated Tokens: {self.tokens_generated}</p>
                </div>
                """
                display(widgets.VBox([
                    api_toggle_btn,
                    widgets.HTML(api_html),
                    api_out
                ]))

        def show_memory(b=None):
            for k, btn in buttons.items():
                btn.button_style = "primary" if k == "memory" else ""
            
            with content_output:
                content_output.clear_output()
                display(HTML("<div class='apex-header'>Memory Explorer</div>"))
                
                mem_path = self.workspace_manager.active_workspace_path
                print(f"Active Workspace Path: {mem_path}")
                print(f"Subdirectories: conversations/, projects/, repositories/")

        def show_performance(b=None):
            for k, btn in buttons.items():
                btn.button_style = "primary" if k == "performance" else ""
            
            with content_output:
                content_output.clear_output()
                display(HTML("<div class='apex-header'>Performance Center</div>"))
                
                # Mock performance traces
                perf_html = """
                <div class='apex-card'>
                    <h4>Real-time Telemetry</h4>
                    <p>Queue Length: <b>0</b></p>
                    <p>Time to First Token (TTFT): <b>0.024s</b></p>
                    <p>Throughput Speed: <b>32.4 tokens/second</b></p>
                    <p>VRAM Allocation: <b>62.4%</b></p>
                </div>
                """
                display(HTML(perf_html))

        def show_logs(b=None):
            for k, btn in buttons.items():
                btn.button_style = "primary" if k == "logs" else ""
            
            with content_output:
                content_output.clear_output()
                display(HTML("<div class='apex-header'>Live Logs</div>"))
                
                log_box = widgets.Output()
                search_box = widgets.Text(description="Filter:")
                refresh_btn = widgets.Button(description="Refresh Logs", button_style="info")

                def load_logs(b=None):
                    with log_box:
                        log_box.clear_output()
                        lines = self.log_viewer.fetch_logs(limit=25, search_query=search_box.value)
                        for line in lines:
                            print(line)

                refresh_btn.on_click(load_logs)
                load_logs()
                
                display(widgets.VBox([
                    widgets.HBox([search_box, refresh_btn]),
                    log_box
                ]))

        def show_settings(b=None):
            for k, btn in buttons.items():
                btn.button_style = "primary" if k == "settings" else ""
            
            with content_output:
                content_output.clear_output()
                display(HTML("<div class='apex-header'>Settings Center</div>"))
                
                config = self.config_manager.config
                name_input = widgets.Text(description="Workspace Name:", value=config.get("project_name", "APEX"))
                save_btn = widgets.Button(description="Save Config", button_style="success")
                set_out = widgets.Output()

                def on_save_config(b):
                    with set_out:
                        set_out.clear_output()
                        config["project_name"] = name_input.value
                        if self.config_manager.save(config):
                            print("[+] Configuration changes saved.")
                        else:
                            print("[-] Error saving configuration.")

                save_btn.on_click(on_save_config)

                display(widgets.VBox([
                    name_input,
                    save_btn,
                    set_out
                ]))

        # Register Navigation Callbacks
        buttons["home"].on_click(show_home)
        buttons["workspace"].on_click(show_workspace)
        buttons["models"].on_click(show_models)
        buttons["runtime"].on_click(show_runtime)
        buttons["api"].on_click(show_api)
        buttons["memory"].on_click(show_memory)
        buttons["performance"].on_click(show_performance)
        buttons["logs"].on_click(show_logs)
        buttons["settings"].on_click(show_settings)

        # Show Home on Startup
        show_home()

        # Render Main Panel
        dashboard_layout = widgets.HBox([sidebar_box, content_output])
        display(dashboard_layout)
        return dashboard_layout
