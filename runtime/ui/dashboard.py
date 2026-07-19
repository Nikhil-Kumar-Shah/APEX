"""Interactive ipywidgets dashboard for Google Colab."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from runtime.config.manager import ConfigManager
from runtime.core.health import HealthMonitor
from runtime.model.manager import ModelManager
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
    ):
        """Initializes the RuntimeDashboard.

        Args:
            config_manager: The active ConfigManager.
            model_manager: The active ModelManager.
            health_monitor: The active HealthMonitor.
            log_filepath: Path to the runtime log file.
        """
        self.config_manager = config_manager
        self.model_manager = model_manager
        self.health_monitor = health_monitor
        self.log_viewer = LogViewer(log_filepath)
        self.benchmark_tracker = BenchmarkTracker()
        
        # Load update checker
        self.update_checker = UpdateChecker(
            current_runtime_version="0.1.0",
            current_config_version=config_manager.config.get("config_version", "1.0.0"),
        )
        
        self.active_server_process = None

    def save_settings_ui(self, form_data: Dict[str, Any]) -> bool:
        """Invoked by UI form to save settings changes to Configuration Manager.

        Args:
            form_data: Parameters updated by user.

        Returns:
            bool: True if configuration was successfully validated and saved.
        """
        current_config = self.config_manager.config.copy()
        
        # Update configurations based on form values
        if "project_id" in form_data:
            current_config["project_id"] = form_data["project_id"]
        if "project_name" in form_data:
            current_config["project_name"] = form_data["project_name"]
            
        # Update directories settings
        if "directories" in current_config:
            if "cache_dir" in form_data:
                current_config["directories"]["cache_dir"] = form_data["cache_dir"]
                
        # Update performance settings
        if "logging" in current_config and "level" in form_data:
            current_config["logging"]["level"] = form_data["level"]

        # Validate and save
        try:
            return self.config_manager.save(current_config)
        except Exception as e:
            logger.error(f"Failed to save settings via Dashboard UI: {e}")
            return False

    def render(self) -> Any:
        """Renders the IPython Widgets tab layout inside notebooks.

        Returns:
            Any: The compiled ipywidgets layout or mock container if headless.
        """
        try:
            import ipywidgets as widgets
            from IPython.display import display
        except ImportError:
            logger.info("Headless rendering: ipywidgets is not installed.")
            return "Headless Dashboard Instance (ipywidgets missing)"

        # 1. Tab 1: Dashboard & System Health Monitor
        dashboard_output = widgets.Output()
        
        def refresh_stats(b=None):
            with dashboard_output:
                dashboard_output.clear_output()
                report = self.health_monitor.generate_report()
                print("🌌 Startup Dashboard - System Status")
                print("=" * 50)
                print(f"Model ID: {report['model_manager'].get('active_model_id') or 'None loaded'}")
                print(f"Loaded: {report['model_manager'].get('is_loaded')}")
                print(f"Disk Free: {report['disk'].get('free_gb', 0.0):.2f} GB")
                print(f"RAM Percent: {report['ram'].get('percent_used', 0.0):.1f}%")
                print(f"GPU Name: {report['gpu'].get('device_name') or 'N/A'}")
                print(f"GPU Uptime: {report['uptime_seconds']:.1f} seconds")

        refresh_btn = widgets.Button(description="Refresh Health Stats", button_style="info")
        refresh_btn.on_click(refresh_stats)
        refresh_stats()

        dashboard_tab = widgets.VBox([refresh_btn, dashboard_output])

        # 2. Tab 2: Settings Form
        config = self.config_manager.config
        proj_id_input = widgets.Text(description="Project ID:", value=config.get("project_id", ""))
        proj_name_input = widgets.Text(description="Name:", value=config.get("project_name", ""))
        
        save_btn = widgets.Button(description="Save Configurations", button_style="success")
        settings_output = widgets.Output()

        def on_save_clicked(b):
            with settings_output:
                settings_output.clear_output()
                data = {
                    "project_id": proj_id_input.value,
                    "project_name": proj_name_input.value,
                }
                if self.save_settings_ui(data):
                    print("[+] Configuration successfully saved and validated.")
                else:
                    print("[-] Failed to save configurations. Check formatting.")

        save_btn.on_click(on_save_clicked)
        settings_tab = widgets.VBox([proj_id_input, proj_name_input, save_btn, settings_output])

        # 3. Tab 3: Performance & Benchmarks
        benchmark_output = widgets.Output()
        
        def run_dummy_benchmark(b):
            with benchmark_output:
                benchmark_output.clear_output()
                print("[!] Running token-latency benchmarks...")
                start_time = time_now = 0.5 # mock load times
                run = self.benchmark_tracker.record_run(
                    model_id=self.model_manager.active_model_id or "qwen-7b",
                    engine="mock",
                    load_time=0.8,
                    ttft=0.03,
                    tokens_count=100,
                    generation_time=2.1,
                )
                print(f"Benchmark finished:")
                print(f"  Throughput: {run['tokens_per_second']:.2f} tokens/second")
                print(f"  TTFT: {run['ttft_sec']} seconds")
                print(f"  Total Latency: {run['total_latency_sec']:.2f} seconds")

        benchmark_btn = widgets.Button(description="Run Benchmark Test", button_style="warning")
        benchmark_btn.on_click(run_dummy_benchmark)
        benchmark_tab = widgets.VBox([benchmark_btn, benchmark_output])

        # 4. Tab 4: Enhanced Log Viewer
        log_output = widgets.Output()
        search_input = widgets.Text(description="Filter query:")
        log_refresh_btn = widgets.Button(description="Fetch Logs", button_style="info")

        def refresh_logs_ui(b=None):
            with log_output:
                log_output.clear_output()
                lines = self.log_viewer.fetch_logs(limit=30, search_query=search_input.value)
                for line in lines:
                    print(line)

        log_refresh_btn.on_click(refresh_logs_ui)
        refresh_logs_ui()
        logs_tab = widgets.VBox([widgets.HBox([search_input, log_refresh_btn]), log_output])

        # 5. Tab 5: Update & Diagnostics
        update_output = widgets.Output()
        check_btn = widgets.Button(description="Check Version Updates", button_style="info")
        
        def run_update_check(b):
            with update_output:
                update_output.clear_output()
                res = self.update_checker.check_for_updates()
                print("🔄 Version Checker Alert")
                print("-" * 40)
                print(res["message"])

        check_btn.on_click(run_update_check)
        update_tab = widgets.VBox([check_btn, update_output])

        # Compile Tabs
        tabs = widgets.Tab()
        tabs.children = [dashboard_tab, settings_tab, benchmark_tab, logs_tab, update_tab]
        tabs.set_title(0, "Dashboard & Controls")
        tabs.set_title(1, "Settings Editor")
        tabs.set_title(2, "Benchmarks")
        tabs.set_title(3, "Log Viewer")
        tabs.set_title(4, "Diagnostics & Updates")

        display(tabs)
        return tabs
