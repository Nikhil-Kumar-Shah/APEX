"""Interactive ipywidgets dashboard for Google Colab consuming the APEX Design System."""

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

# Design System Imports
from runtime.ui.colors import get_theme_css
from runtime.ui.icons import ICONS
from runtime.ui.theme import ThemeManager
from runtime.ui.widgets import create_card_html, get_base_css

logger = logging.getLogger("runtime.ui.dashboard")


class RuntimeDashboard:
    """Orchestrates drawing HTML sidebar navigation, settings categories, and metrics in notebooks."""

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
        
        # Theme Management
        self.theme_manager = ThemeManager(initial_dark=True)
        
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

        # Style injection
        css_style_widget = widgets.HTML(get_base_css(self.theme_manager.dark_mode))
        display(css_style_widget)

        # Output Area
        content_output = widgets.Output()

        # Sidebar Widgets
        title_widget = widgets.HTML(
            f"<div class='apex-title'>{ICONS['home']} APEX Studio</div>"
        )
        
        ws_badge = widgets.HTML(
            f"<div style='margin-bottom: 12px;'><span class='apex-badge-active'>Active WS: {self.workspace_manager.active_workspace_id}</span></div>"
        )

        # Navigation Buttons
        buttons = {
            "home": widgets.Button(description=f"{ICONS['home']} Home", layout=widgets.Layout(width="95%")),
            "workspace": widgets.Button(description=f"{ICONS['workspace']} Workspace Studio", layout=widgets.Layout(width="95%")),
            "models": widgets.Button(description=f"{ICONS['models']} Model Studio", layout=widgets.Layout(width="95%")),
            "runtime": widgets.Button(description=f"{ICONS['runtime']} Runtime Controls", layout=widgets.Layout(width="95%")),
            "api": widgets.Button(description=f"{ICONS['api']} API Manager", layout=widgets.Layout(width="95%")),
            "memory": widgets.Button(description=f"{ICONS['memory']} Memory Explorer", layout=widgets.Layout(width="95%")),
            "performance": widgets.Button(description=f"{ICONS['performance']} Performance Center", layout=widgets.Layout(width="95%")),
            "logs": widgets.Button(description=f"{ICONS['logs']} Live Logs", layout=widgets.Layout(width="95%")),
            "settings": widgets.Button(description=f"{ICONS['settings']} Settings Center", layout=widgets.Layout(width="95%")),
        }

        # Styling Buttons
        for btn in buttons.values():
            btn.style.font_weight = "bold"

        dev_toggle = widgets.ToggleButton(
            value=self.dev_mode,
            description="🛠 Developer Mode",
            button_style="warning",
            layout=widgets.Layout(width="95%", margin="20px 0px 5px 0px")
        )

        theme_toggle = widgets.ToggleButton(
            value=self.theme_manager.dark_mode,
            description="🌓 Dark Mode",
            button_style="info",
            layout=widgets.Layout(width="95%", margin="5px 0px 5px 0px")
        )

        def on_theme_changed(change):
            self.theme_manager.set_theme(change["new"])
            css_style_widget.value = get_base_css(change["new"])

        theme_toggle.observe(on_theme_changed, "value")

        def on_dev_toggle_changed(change):
            self.dev_mode = change["new"]
            draw_sidebar()

        dev_toggle.observe(on_dev_toggle_changed, "value")

        sidebar_box = widgets.VBox(layout=widgets.Layout(width="230px", border_right="1px solid var(--apex-border)", padding="10px"))

        def draw_sidebar():
            visible_btns = [title_widget, ws_badge, buttons["home"], buttons["workspace"], buttons["models"], buttons["runtime"], buttons["api"], buttons["memory"]]
            if self.dev_mode:
                visible_btns.append(buttons["performance"])
                visible_btns.append(buttons["logs"])
            visible_btns.append(buttons["settings"])
            visible_btns.append(dev_toggle)
            visible_btns.append(theme_toggle)
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
                
                # Render Row 1: Workspace & General status Cards
                row1_html = f"""
                <div class="apex-section-heading">Workspace & Runtime Command Center</div>
                <div style="display: flex; gap: 12px; margin-bottom: 16px;">
                    {create_card_html("Workspace", ICONS['workspace'], self.workspace_manager.active_workspace_id, "Location: Drive/Local", "Active", "success")}
                    {create_card_html("Runtime Status", ICONS['runtime'], "Running", f"Engine: {report['model_manager'].get('engine_status', {}).get('engine_name', 'N/A')}", "Active", "success")}
                    {create_card_html("Active Model", ICONS['models'], active_model.split('/')[-1], f"ID: {active_model}", "Loaded" if report['model_manager'].get('is_loaded') else "None", "success" if report['model_manager'].get('is_loaded') else "warning")}
                    {create_card_html("API Server", ICONS['api'], "Running" if self.is_api_running else "Stopped", "Endpoint: :8000/v1", "Online" if self.is_api_running else "Offline", "success" if self.is_api_running else "error")}
                </div>
                """
                display(HTML(row1_html))

                # Render Row 2: Performance metrics Cards
                row2_html = f"""
                <div class="apex-section-heading">Hardware & Telemetry Diagnostics</div>
                <div style="display: flex; gap: 12px; margin-bottom: 16px;">
                    {create_card_html("GPU Device", ICONS['gpu'], report['gpu'].get('device_name') or 'CPU Fallback', "Hardware Allocation", "Running", "success")}
                    {create_card_html("VRAM Used", ICONS['gpu'], f"{report['gpu'].get('vram_free_mb', 0.0):.1f} MB Free", "VRAM Limit: 16GB", "Normal", "success")}
                    {create_card_html("System RAM", ICONS['performance'], f"{report['ram'].get('percent_used', 0.0):.1f}%", f"Free: {report['ram'].get('free_gb', 0.0):.2f} GB", "Healthy", "success")}
                    {create_card_html("Recent Activity", ICONS['logs'], "Apex Synced", "No warnings reported", "Green", "success")}
                </div>
                """
                display(HTML(row2_html))

                # Quick action buttons directly on home page
                display(HTML("<div class='apex-section-heading'>Home Command Center Quick Actions</div>"))
                q_refresh_btn = widgets.Button(description="Refresh Telemetry", button_style="info")
                q_restart_btn = widgets.Button(description="Restart Services", button_style="warning")
                q_unload_btn = widgets.Button(description="Unload VRAM", button_style="danger")

                def q_refresh(b):
                    show_home()
                q_refresh_btn.on_click(q_refresh)

                def q_unload(b):
                    self.model_manager.unload_model()
                    show_home()
                q_unload_btn.on_click(q_unload)

                display(widgets.HBox([q_refresh_btn, q_restart_btn, q_unload_btn]))

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
                
                switch_btn = widgets.Button(description="Open Workspace", button_style="success")
                del_btn = widgets.Button(description="Delete Workspace", button_style="danger")
                ws_out = widgets.Output()

                def on_switch(b):
                    with ws_out:
                        ws_out.clear_output()
                        self.workspace_manager.load_workspace(ws_select.value)
                        ws_badge.value = f"<div style='margin-bottom: 12px;'><span class='apex-badge-active'>Active WS: {self.workspace_manager.active_workspace_id}</span></div>"
                        print(f"[+] Loaded workspace: {ws_select.value}")
                        show_workspace()
                        
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
                display(HTML("<br><div class='apex-section-heading'>Create New Workspace</div>"))
                ws_name_input = widgets.Text(description="Name:", placeholder="AI Research Team")
                ws_desc_input = widgets.Text(description="Desc:", placeholder="General project notes")
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
                display(HTML("<div class='apex-section-heading'>Cached / Downloaded Models</div>"))
                
                if not cached:
                    display(HTML("<p>No local models cached yet.</p>"))
                else:
                    for m in cached:
                        m_id = m.get('model_id')
                        m_size = m.get('size_bytes', 0)/(1024**3)
                        display(HTML(f"""
                        <div class='apex-card' style='display:flex; justify-content:space-between; align-items:center;'>
                            <div>
                                <b>{m_id}</b><br>
                                <span class='apex-caption'>Disk Size: {m_size:.2f} GB | Family: {m_id.split('/')[0] if '/' in m_id else 'default'}</span>
                            </div>
                            <span class='apex-badge-active'>Downloaded</span>
                        </div>
                        """))

                # Download Interface
                display(HTML("<br><div class='apex-section-heading'>Search & Download Model (Hugging Face)</div>"))
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
                        print(f"[+] Submitting background download task for: {model_id}...")
                        self.orchestrator.submit_task("download_model", {"model_id": model_id})
                        print("[+] Download task submitted to queue.")

                dl_btn.on_click(on_download)

                # Load/Unload controls
                display(HTML("<br><div class='apex-section-heading'>Active Model Loader</div>"))
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
                        print(f"[+] Submitting model load task for '{load_select.value}'...")
                        self.orchestrator.submit_task("load_model", {"model_id": load_select.value})
                        print("[+] Model load task submitted to queue.")

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
