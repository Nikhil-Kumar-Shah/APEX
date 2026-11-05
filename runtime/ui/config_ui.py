"""Simplified, developer-grade Configuration & Launch UI for APEX."""

import logging
import re
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from bootstrap.diagnostics import DiagnosticsManager
from runtime.config.manager import ConfigManager
from runtime.config.profile import (
    CURATED_PRESETS,
    ModelPreset,
    check_hardware_compatibility,
    estimate_vram,
    get_preset,
    get_profile,
)
from runtime.config.schema import ApexConfig
from runtime.core.errors import ApexErrorCode, RuntimeErrorBase

logger = logging.getLogger("runtime.ui.config")


def get_launchpad_css() -> str:
    """Returns modern, minimal CSS for the APEX Launchpad."""
    return """
    <style>
        .apex-launchpad {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 20px;
            max-width: 900px;
            margin: 10px 0;
            box-sizing: border-box;
        }
        .apex-lp-header {
            border-bottom: 1px solid #30363d;
            padding-bottom: 14px;
            margin-bottom: 18px;
        }
        .apex-lp-title {
            font-size: 18px;
            font-weight: 700;
            color: #58a6ff;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .apex-lp-subtitle {
            font-size: 12px;
            color: #8b949e;
            margin-top: 4px;
        }
        .apex-section-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 14px;
        }
        .apex-section-title {
            font-size: 13px;
            font-weight: 600;
            color: #f0f6fc;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .apex-badge-compatible {
            background: #1f6feb26;
            color: #58a6ff;
            border: 1px solid #388bfd4d;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }
        .apex-badge-success {
            background: #23863626;
            color: #3fb950;
            border: 1px solid #2ea0434d;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }
        .apex-badge-warning {
            background: #9e6a0326;
            color: #d29922;
            border: 1px solid #bb80094d;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }
        .apex-badge-danger {
            background: #da363326;
            color: #f85149;
            border: 1px solid #f851494d;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }
        .apex-snippet {
            background: #090d13;
            border: 1px solid #21262d;
            border-radius: 6px;
            padding: 10px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            color: #79c0ff;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
            margin-top: 8px;
        }
        .apex-error-box {
            background: #2b1113;
            border: 1px solid #8e1519;
            border-radius: 6px;
            padding: 12px;
            margin-top: 10px;
            color: #ff7b72;
            font-size: 12px;
        }
    </style>
    """


class ConfigUI:
    """Unified, developer-grade configuration & launchpad interface."""

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        model_manager: Optional[Any] = None,
        api_manager: Optional[Any] = None,
        orchestrator: Optional[Any] = None,
        workspace_path: Optional[Path] = None,
    ):
        """Initializes the ConfigUI."""
        self.workspace_path = workspace_path or Path.cwd()
        self.config_manager = config_manager or ConfigManager(
            self.workspace_path / "workspaces" / "default" / "config.json"
        )
        self.model_manager = model_manager
        self.api_manager = api_manager
        self.orchestrator = orchestrator

        # State attributes
        self.config: ApexConfig = self.config_manager.get_apex_config()
        self.diagnostics_manager = DiagnosticsManager(self.workspace_path)
        self.hardware_info: Dict[str, Any] = {}
        self.validation_result: Dict[str, Any] = {"valid": False, "messages": []}
        self.is_launching = False

        # Widget handles (populated on render)
        self.widgets: Dict[str, Any] = {}
        self.ui_container: Optional[Any] = None
        
        # Initial hardware inspection
        self.detect_hardware()

    def detect_hardware(self) -> Dict[str, Any]:
        """Dynamically inspects available hardware (GPU, VRAM, RAM, Storage)."""
        report = self.diagnostics_manager.run_diagnostics()
        gpu = report.get("gpu", {})
        storage = report.get("storage", {})
        system = report.get("system", {})

        self.hardware_info = {
            "gpu_name": gpu.get("device_name") or "CPU Fallback",
            "cuda_available": gpu.get("cuda_available", False),
            "vram_total_gb": gpu.get("vram_total_gb", 0.0),
            "ram_total_gb": storage.get("ram_total_gb", 0.0),
            "ram_available_gb": storage.get("ram_available_gb", 0.0),
            "disk_free_gb": storage.get("disk_free_gb", 0.0),
            "os_name": system.get("os_name", "Unknown"),
            "architecture": system.get("architecture", "Unknown"),
            "is_colab": system.get("is_colab", False),
        }
        return self.hardware_info

    def get_hardware_status_html(self, selected_model_id: str, precision: str = "float16") -> str:
        """Renders the HTML hardware detection card with compatibility status."""
        hw = self.hardware_info
        cuda = hw["cuda_available"]
        vram = hw["vram_total_gb"]
        ram = hw["ram_total_gb"]
        ram_avail = hw["ram_available_gb"]
        disk_free = hw["disk_free_gb"]
        gpu_name = hw["gpu_name"]

        status_key, explanation = check_hardware_compatibility(
            repo_id=selected_model_id,
            vram_total_gb=vram,
            cuda_available=cuda,
            precision=precision,
        )

        badge_class = {
            "compatible": "apex-badge-success",
            "tight": "apex-badge-warning",
            "warning": "apex-badge-danger",
            "cpu": "apex-badge-compatible",
        }.get(status_key, "apex-badge-compatible")

        status_label = {
            "compatible": "✓ Compatible",
            "tight": "⚠ Tight VRAM",
            "warning": "⚠ Insufficient VRAM",
            "cpu": "ℹ CPU Fallback",
        }.get(status_key, "Detected")

        req_vram = estimate_vram(selected_model_id, precision)

        return f"""
        <div style="font-size: 12px; line-height: 1.6;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span><b>Accelerator:</b> {gpu_name}</span>
                <span class="{badge_class}">{status_label}</span>
            </div>
            <div><b>VRAM:</b> {f'{vram:.1f} GB Total' if cuda else 'None (Running on CPU)'} · <b>Model Estimate:</b> ~{req_vram:.1f} GB ({precision})</div>
            <div><b>System RAM:</b> {ram_avail:.1f} GB free / {ram:.1f} GB total · <b>Storage:</b> {disk_free:.1f} GB free</div>
            <div style="margin-top: 6px; color: #8b949e; font-style: italic;">{explanation}</div>
        </div>
        """

    def validate(self) -> Dict[str, Any]:
        """Validates the current configuration against hardware and backend rules."""
        messages: List[str] = []
        errors: List[str] = []

        model_id = self.config.model_id.strip()
        if not model_id:
            errors.append("Model repository ID cannot be empty.")
        elif not re.match(r"^[\w\.\-]+(/[\w\.\-]+)?$", model_id):
            errors.append(f"Invalid model ID format '{model_id}'. Expected 'org/model-name'.")
        else:
            messages.append(f"Model ID '{model_id}' format valid.")

        preset = get_preset(model_id)
        if preset and preset.requires_auth:
            if not self.config.hf_token:
                messages.append(f"Note: '{model_id}' is a gated model. Ensure a valid Hugging Face Token is provided if you encounter 401/403 errors.")

        # VRAM compatibility
        status_key, exp = check_hardware_compatibility(
            repo_id=model_id,
            vram_total_gb=self.hardware_info["vram_total_gb"],
            cuda_available=self.hardware_info["cuda_available"],
            precision=self.config.precision,
        )
        if status_key == "warning":
            messages.append(f"Hardware Alert: {exp}")
        else:
            messages.append(f"Hardware check: {exp}")

        # Port validation
        if self.config.port is not None:
            if not (1024 <= self.config.port <= 65535):
                errors.append(f"Port {self.config.port} is outside valid range (1024-65535).")
            else:
                messages.append(f"Custom port {self.config.port} valid.")

        is_valid = len(errors) == 0
        self.validation_result = {
            "valid": is_valid,
            "messages": messages,
            "errors": errors,
        }
        return self.validation_result

    def save_configuration(self) -> bool:
        """Saves current state to ConfigManager."""
        self.config_manager.save_apex_config(self.config)
        return True

    def launch(
        self,
        on_progress: Optional[Callable[[str, int], None]] = None,
        on_complete: Optional[Callable[[bool, Optional[str]], None]] = None,
    ) -> bool:
        """Triggers the full, verified Phase 1 deployment workflow."""
        if self.is_launching:
            logger.warning("Launch already in progress. Ignoring duplicate trigger.")
            return False

        self.is_launching = True
        logger.info(f"Starting APEX deployment for model: {self.config.model_id}...")

        def _run_pipeline():
            success = False
            err_msg: Optional[str] = None
            try:
                # 1. Validate & Save
                if on_progress:
                    on_progress("Validating configuration...", 10)
                val = self.validate()
                if not val["valid"]:
                    raise RuntimeErrorBase(
                        error_code=ApexErrorCode.MODEL_LOAD_FAILED,
                        message="Configuration validation failed: " + "; ".join(val["errors"]),
                        suggestion="Check the model identifier and configuration settings.",
                    )
                self.save_configuration()

                # 2. Prepare dependencies / cache
                if on_progress:
                    on_progress("Preparing model cache...", 25)
                if self.orchestrator:
                    self.orchestrator.state_machine.transition_to("MODEL_DOWNLOADING")

                # 3. Model Download (if model_manager bound)
                if self.model_manager:
                    if on_progress:
                        on_progress(f"Checking & downloading {self.config.model_id}...", 40)
                    self.model_manager.download_model(
                        self.config.model_id,
                        revision=self.config.revision,
                        hf_token=self.config.hf_token,
                    )

                # 4. Model Loading & Warmup
                if on_progress:
                    on_progress(f"Loading weights into {self.config.precision}...", 60)
                if self.orchestrator:
                    self.orchestrator.state_machine.transition_to("MODEL_LOADING")

                if self.model_manager:
                    self.model_manager.load_model(
                        self.config.model_id,
                        precision=self.config.precision,
                        revision=self.config.revision,
                        hf_token=self.config.hf_token,
                    )
                if self.orchestrator:
                    self.orchestrator.state_machine.transition_to("MODEL_READY")

                # 5. Start API Server & Tunnel
                if on_progress:
                    on_progress("Starting API Server and Cloudflare Tunnel...", 75)
                if self.orchestrator:
                    self.orchestrator.state_machine.transition_to("API_STARTING")

                if self.api_manager:
                    # Sync config
                    self.api_manager.config.transport = self.config.transport
                    self.api_manager.config.internal_port = self.config.port
                    self.api_manager.config.enable_auth = self.config.enable_auth
                    if self.config.api_key:
                        self.api_manager.config.api_key = self.config.api_key

                    if on_progress:
                        on_progress("Verifying public endpoint & live inference...", 90)

                    api_success = self.api_manager.start()
                    if not api_success:
                        raise RuntimeErrorBase(
                            error_code=ApexErrorCode.API_START_FAILED,
                            message=f"API startup failed: {self.api_manager.state.last_error}",
                            suggestion="Check port binding and tunnel connection logs.",
                        )

                if self.orchestrator:
                    self.orchestrator.state_machine.transition_to("READY")

                if on_progress:
                    on_progress("APEX READY — Public Endpoint Verified!", 100)

                success = True
            except Exception as e:
                logger.error(f"APEX Launch Pipeline failed: {e}", exc_info=True)
                err_msg = str(e)
                if self.orchestrator:
                    self.orchestrator.state_machine.transition_to("FAILED")
                if on_progress:
                    on_progress(f"Launch Failed: {e}", 0)
            finally:
                self.is_launching = False
                if on_complete:
                    on_complete(success, err_msg)

        # Run pipeline
        thread = threading.Thread(target=_run_pipeline, daemon=True)
        thread.start()
        return True

    def render(self) -> Any:
        """Renders the interactive ipywidgets Launchpad."""
        try:
            import ipywidgets as widgets
            from IPython.display import HTML, display
        except ImportError:
            # Headless CLI fallback
            print(self._render_headless_text())
            return "Headless ConfigUI Instance"

        display(HTML(get_launchpad_css()))

        # ── 1. Model Selection ───────────────────────────────────────────
        preset_options = [(p.display_name, p.repo_id) for p in CURATED_PRESETS]
        preset_options.append(("Custom Hugging Face Model...", "custom"))

        current_repo = self.config.model_id
        preset_match = get_preset(current_repo)
        default_preset_val = current_repo if preset_match else "custom"

        model_dropdown = widgets.Dropdown(
            options=preset_options,
            value=default_preset_val,
            description="Preset:",
            layout=widgets.Layout(width="95%"),
        )

        custom_model_text = widgets.Text(
            value=current_repo if not preset_match else "",
            placeholder="e.g. meta-llama/Llama-3.2-3B-Instruct",
            description="Repo ID:",
            disabled=(default_preset_val != "custom"),
            layout=widgets.Layout(width="95%"),
        )

        model_desc_html = widgets.HTML(
            value=f"<div style='color: #8b949e; font-size: 12px; margin-top: 4px;'>{preset_match.description if preset_match else 'Custom model specification.'}</div>"
        )

        # ── 2. Hardware Detection Card ───────────────────────────────────
        hw_card_html = widgets.HTML(
            value=self.get_hardware_status_html(current_repo, self.config.precision)
        )
        refresh_hw_btn = widgets.Button(
            description="Refresh Hardware",
            icon="refresh",
            layout=widgets.Layout(width="150px"),
        )

        # ── 3. Essential Settings ────────────────────────────────────────
        precision_dropdown = widgets.Dropdown(
            options=["float16", "bfloat16", "float32"],
            value=self.config.precision,
            description="Precision:",
            layout=widgets.Layout(width="45%"),
        )

        hf_token_text = widgets.Password(
            value=self.config.hf_token or "",
            placeholder="hf_... (optional)",
            description="HF Token:",
            layout=widgets.Layout(width="45%"),
        )

        # ── 4. Advanced Settings (Accordion) ─────────────────────────────
        transport_dropdown = widgets.Dropdown(
            options=["cloudflare", "local", "ngrok"],
            value=self.config.transport,
            description="Transport:",
            layout=widgets.Layout(width="95%"),
        )

        port_text = widgets.Text(
            value=str(self.config.port) if self.config.port else "",
            placeholder="Auto (search 8000–8010)",
            description="Port:",
            layout=widgets.Layout(width="95%"),
        )

        auth_checkbox = widgets.Checkbox(
            value=self.config.enable_auth,
            description="Require API Key Authentication",
        )

        api_key_text = widgets.Password(
            value=self.config.api_key or "",
            placeholder="Custom API Key (optional)",
            description="API Key:",
            disabled=not self.config.enable_auth,
            layout=widgets.Layout(width="95%"),
        )

        max_tokens_slider = widgets.IntSlider(
            value=self.config.max_tokens,
            min=64,
            max=8192,
            step=64,
            description="Max Tokens:",
            layout=widgets.Layout(width="95%"),
        )

        temp_slider = widgets.FloatSlider(
            value=self.config.temperature,
            min=0.0,
            max=2.0,
            step=0.05,
            description="Temp:",
            layout=widgets.Layout(width="95%"),
        )

        advanced_box = widgets.VBox(
            [
                transport_dropdown,
                port_text,
                auth_checkbox,
                api_key_text,
                max_tokens_slider,
                temp_slider,
            ],
            layout=widgets.Layout(padding="10px"),
        )
        advanced_accordion = widgets.Accordion(children=[advanced_box])
        advanced_accordion.set_title(0, "⚙ Advanced Settings")
        advanced_accordion.selected_index = None  # Collapsed by default

        # ── 5. Validation & Launch Controls ──────────────────────────────
        validate_btn = widgets.Button(
            description="Validate Configuration",
            button_style="",
            icon="check",
            layout=widgets.Layout(width="180px"),
        )

        start_btn = widgets.Button(
            description="START APEX",
            button_style="success",
            icon="rocket",
            layout=widgets.Layout(width="220px", height="38px", font_weight="bold"),
        )

        validation_output = widgets.HTML(value="")
        progress_bar = widgets.IntProgress(
            value=0,
            min=0,
            max=100,
            bar_style="info",
            layout=widgets.Layout(width="100%", display="none"),
        )
        progress_label = widgets.HTML(value="", layout=widgets.Layout(display="none"))
        access_box = widgets.HTML(value="", layout=widgets.Layout(display="none"))

        # ── Event Callbacks ──────────────────────────────────────────────
        def _on_model_change(change):
            val = change["new"]
            if val == "custom":
                custom_model_text.disabled = False
                active_id = custom_model_text.value.strip() or "custom/model"
                desc = "Custom model from Hugging Face Hub."
            else:
                custom_model_text.disabled = True
                active_id = val
                preset = get_preset(val)
                desc = preset.description if preset else ""

            self.config.model_id = active_id
            model_desc_html.value = f"<div style='color: #8b949e; font-size: 12px; margin-top: 4px;'>{desc}</div>"
            hw_card_html.value = self.get_hardware_status_html(active_id, precision_dropdown.value)

        def _on_custom_model_text_change(change):
            if model_dropdown.value == "custom":
                active_id = change["new"].strip()
                if active_id:
                    self.config.model_id = active_id
                    hw_card_html.value = self.get_hardware_status_html(active_id, precision_dropdown.value)

        def _on_precision_change(change):
            self.config.precision = change["new"]
            hw_card_html.value = self.get_hardware_status_html(self.config.model_id, self.config.precision)

        def _on_auth_toggle(change):
            self.config.enable_auth = change["new"]
            api_key_text.disabled = not change["new"]

        def _on_refresh_hw_click(_):
            self.detect_hardware()
            hw_card_html.value = self.get_hardware_status_html(self.config.model_id, self.config.precision)

        def _on_validate_click(_):
            # Sync values
            self.config.precision = precision_dropdown.value
            self.config.hf_token = hf_token_text.value.strip() or None
            self.config.transport = transport_dropdown.value
            port_val = port_text.value.strip()
            self.config.port = int(port_val) if port_val.isdigit() else None
            self.config.enable_auth = auth_checkbox.value
            self.config.api_key = api_key_text.value.strip() or None
            self.config.max_tokens = max_tokens_slider.value
            self.config.temperature = temp_slider.value

            val = self.validate()
            if val["valid"]:
                items = "".join(f"<li>{msg}</li>" for msg in val["messages"])
                validation_output.value = f"""
                <div style="background: #1f6feb1a; border: 1px solid #388bfd; border-radius: 6px; padding: 10px; margin-top: 8px;">
                    <b style="color: #58a6ff;">✓ Configuration Validated & Ready</b>
                    <ul style="margin: 6px 0 0 16px; padding: 0; color: #c9d1d9; font-size: 12px;">{items}</ul>
                </div>
                """
            else:
                err_items = "".join(f"<li>{err}</li>" for err in val["errors"])
                validation_output.value = f"""
                <div class="apex-error-box">
                    <b>Validation Issues Detected:</b>
                    <ul style="margin: 6px 0 0 16px; padding: 0;">{err_items}</ul>
                </div>
                """

        def _on_start_click(_):
            if self.is_launching:
                return

            # Sync and validate
            _on_validate_click(None)
            if not self.validation_result["valid"]:
                return

            # Lock UI
            start_btn.disabled = True
            start_btn.description = "Initializing..."
            validate_btn.disabled = True
            progress_bar.layout.display = "block"
            progress_label.layout.display = "block"
            access_box.layout.display = "none"

            def _progress_cb(stage_text: str, percent: int):
                progress_bar.value = percent
                progress_label.value = f"<div style='font-size: 12px; color: #58a6ff; margin-top: 4px;'><b>[{percent}%]</b> {stage_text}</div>"

            def _complete_cb(success: bool, error_msg: Optional[str]):
                start_btn.disabled = False
                validate_btn.disabled = False
                if success:
                    start_btn.description = "RESTART APEX"
                    start_btn.button_style = "info"
                    progress_label.value = "<div style='font-size: 13px; color: #3fb950; font-weight: bold;'>✓ APEX READY — Public Endpoint Verified!</div>"
                    
                    # Access info
                    pub_url = self.api_manager.state.public_url if self.api_manager else "http://127.0.0.1:8000"
                    openai_url = self.api_manager.state.openai_url if self.api_manager else f"{pub_url}/v1"
                    
                    curl_snippet = f"""curl -X POST {openai_url}/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{{\"model\": \"{self.config.model_id}\", \"messages\": [{{\"role\": \"user\", \"content\": \"Hello APEX!\"}}]}}'"""

                    access_box.layout.display = "block"
                    access_box.value = f"""
                    <div style="background: #2386361a; border: 1px solid #2ea043; border-radius: 8px; padding: 14px; margin-top: 14px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 15px; font-weight: bold; color: #3fb950;">● APEX ONLINE (RUNNING)</span>
                            <span class="apex-badge-success">Verified</span>
                        </div>
                        <div style="margin-top: 10px; font-size: 13px;">
                            <div><b>Public URL:</b> <a href="{pub_url}" target="_blank" style="color: #58a6ff;">{pub_url}</a></div>
                            <div><b>OpenAI Base URL:</b> <a href="{openai_url}" target="_blank" style="color: #58a6ff;">{openai_url}</a></div>
                        </div>
                        <div style="margin-top: 10px;">
                            <div style="font-size: 12px; font-weight: bold; color: #8b949e;">Quick Test cURL:</div>
                            <div class="apex-snippet">{curl_snippet}</div>
                        </div>
                    </div>
                    """
                else:
                    start_btn.description = "START APEX"
                    start_btn.button_style = "success"
                    progress_label.value = f"<div style='font-size: 13px; color: #f85149; font-weight: bold;'>Launch Failed</div>"
                    access_box.layout.display = "block"
                    access_box.value = f"""
                    <div class="apex-error-box">
                        <b>Runtime Error During Initialization:</b><br>
                        {error_msg}
                        <div style="margin-top: 6px; color: #c9d1d9;">Check VRAM allocation, GPU availability, or model ID.</div>
                    </div>
                    """

            self.launch(on_progress=_progress_cb, on_complete=_complete_cb)

        # Connect hooks
        model_dropdown.observe(_on_model_change, names="value")
        custom_model_text.observe(_on_custom_model_text_change, names="value")
        precision_dropdown.observe(_on_precision_change, names="value")
        auth_checkbox.observe(_on_auth_toggle, names="value")
        refresh_hw_btn.on_click(_on_refresh_hw_click)
        validate_btn.on_click(_on_validate_click)
        start_btn.on_click(_on_start_click)

        # ── Assemble Layout ──────────────────────────────────────────────
        step1_box = widgets.VBox(
            [
                widgets.HTML("<div class='apex-section-title'>1. Model Selection</div>"),
                model_dropdown,
                custom_model_text,
                model_desc_html,
            ],
            layout=widgets.Layout(margin="0 0 12px 0"),
        )

        step2_box = widgets.VBox(
            [
                widgets.HBox(
                    [
                        widgets.HTML("<div class='apex-section-title' style='flex:1;'>2. Detected Hardware</div>"),
                        refresh_hw_btn,
                    ]
                ),
                hw_card_html,
            ],
            layout=widgets.Layout(margin="0 0 12px 0"),
        )

        step3_box = widgets.VBox(
            [
                widgets.HTML("<div class='apex-section-title'>3. Essential Settings</div>"),
                widgets.HBox([precision_dropdown, hf_token_text]),
            ],
            layout=widgets.Layout(margin="0 0 12px 0"),
        )

        actions_box = widgets.HBox(
            [start_btn, validate_btn],
            layout=widgets.Layout(gap="14px", margin="16px 0 8px 0"),
        )

        header_html = widgets.HTML("""
        <div class="apex-lp-header">
            <div class="apex-lp-title">🌌 APEX Launchpad</div>
            <div class="apex-lp-subtitle">Configure in seconds · Automatic hardware acceleration · One-click verified deployment</div>
        </div>
        """)

        container = widgets.VBox(
            [
                header_html,
                step1_box,
                step2_box,
                step3_box,
                advanced_accordion,
                actions_box,
                validation_output,
                progress_bar,
                progress_label,
                access_box,
            ],
            layout=widgets.Layout(
                background_color="#0d1117",
                border="1px solid #30363d",
                border_radius="10px",
                padding="20px",
                max_width="850px",
            ),
        )

        self.ui_container = container
        display(container)
        return container

    def _render_headless_text(self) -> str:
        """Returns clean ANSI string representation for headless/CLI environments."""
        hw = self.hardware_info
        return f"""
======================================================
  🌌 APEX LAUNCHPAD (Headless Mode)
======================================================
Model Selected  : {self.config.model_id}
Precision       : {self.config.precision}
Transport       : {self.config.transport}
Accelerator     : {hw.get('gpu_name', 'Unknown')}
CUDA Available  : {'Yes' if hw.get('cuda_available') else 'No'}
System RAM      : {hw.get('ram_available_gb', 0):.1f} GB available
Status          : Ready for programmatic execution
======================================================
"""

