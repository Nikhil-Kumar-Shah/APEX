"""Comprehensive tests for the minimal, professional APEX Notebook Redesign."""

import json
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from runtime.api.manager import APIManager
from runtime.api.state import RuntimeState
from runtime.config.manager import ConfigManager
from runtime.core.lifecycle import RuntimeLifecycle
from runtime.model.manager import ModelManager
from runtime.orchestrator.orchestrator import RuntimeOrchestrator
from runtime.orchestrator.state_machine import RuntimeStateMachine
from runtime.ui.launcher import (
    HF_REPO_PATTERN,
    HF_URL_PATTERN,
    LAUNCH_STAGES,
    APEXLauncher,
    LogBufferHandler,
    detect_environment_hardware,
    get_launcher_css,
    normalize_hf_model_id,
)


# ── 1. Model ID Normalization & Validation Tests ────────────────────────────

def test_normalize_hf_model_id_standard():
    norm, ok, err = normalize_hf_model_id("Qwen/Qwen2.5-1.5B-Instruct")
    assert ok is True
    assert norm == "Qwen/Qwen2.5-1.5B-Instruct"
    assert err is None


def test_normalize_hf_model_id_single_part():
    norm, ok, err = normalize_hf_model_id("gpt2")
    assert ok is True
    assert norm == "gpt2"
    assert err is None


def test_normalize_hf_model_id_full_url():
    url = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct"
    norm, ok, err = normalize_hf_model_id(url)
    assert ok is True
    assert norm == "Qwen/Qwen2.5-1.5B-Instruct"
    assert err is None


def test_normalize_hf_model_id_url_with_subpath():
    url = "https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct/tree/main"
    norm, ok, err = normalize_hf_model_id(url)
    assert ok is True
    assert norm == "meta-llama/Llama-3.2-1B-Instruct"
    assert err is None


def test_normalize_hf_model_id_url_with_git_suffix():
    url = "https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct.git"
    norm, ok, err = normalize_hf_model_id(url)
    assert ok is True
    assert norm == "HuggingFaceTB/SmolLM2-135M-Instruct"
    assert err is None


def test_normalize_hf_model_id_empty():
    norm, ok, err = normalize_hf_model_id("   ")
    assert ok is False
    assert "required" in err.lower() or "empty" in err.lower()


def test_normalize_hf_model_id_non_hf_url():
    url = "https://example.com/some/model"
    norm, ok, err = normalize_hf_model_id(url)
    assert ok is False
    assert "Hugging Face repository URL" in err


def test_normalize_hf_model_id_dangerous_schemes():
    for scheme in ("javascript:alert(1)", "file:///etc/passwd", "data:text/plain;base64,AAA"):
        norm, ok, err = normalize_hf_model_id(scheme)
        assert ok is False
        assert "Invalid" in err


def test_normalize_hf_model_id_invalid_chars():
    norm, ok, err = normalize_hf_model_id("org/model name with spaces$$")
    assert ok is False
    assert "Invalid model ID format" in err


# ── 2. Hardware Detection Tests ─────────────────────────────────────────────

def test_detect_environment_hardware_fields():
    hw = detect_environment_hardware()
    assert isinstance(hw, dict)
    assert "runtime_name" in hw
    assert "device" in hw
    assert "gpu_name" in hw
    assert "ram_total_gb" in hw
    assert "ram_available_gb" in hw
    assert "cuda_available" in hw
    assert isinstance(hw["ram_total_gb"], (int, float))
    assert hw["ram_total_gb"] > 0


# ── 3. Scoped Log Buffer Tests ───────────────────────────────────────────────

def test_log_buffer_handler():
    handler = LogBufferHandler(capacity=50)
    test_logger = logging.getLogger("test_apex_scoped_logger")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)

    test_logger.info("APEX log message 1")
    test_logger.info("APEX log message 2")

    logs = handler.get_logs()
    assert "APEX log message 1" in logs
    assert "APEX log message 2" in logs

    handler.clear()
    assert handler.get_logs() == "No runtime logs recorded yet."


# ── 4. APEXLauncher Validation & Setup Tests ────────────────────────────────

def test_launcher_validation_success(tmp_path: Path):
    launcher = APEXLauncher(workspace_path=tmp_path)
    ok, norm, msgs = launcher.validate_inputs("Qwen/Qwen2.5-0.5B", "float16", "8000")
    assert ok is True
    assert norm == "Qwen/Qwen2.5-0.5B"
    assert len(msgs) > 0


def test_launcher_validation_invalid_model(tmp_path: Path):
    launcher = APEXLauncher(workspace_path=tmp_path)
    ok, norm, msgs = launcher.validate_inputs("bad model $$", "float16", "8000")
    assert ok is False
    assert any("Invalid" in m for m in msgs)


def test_launcher_validation_invalid_port(tmp_path: Path):
    launcher = APEXLauncher(workspace_path=tmp_path)
    ok, norm, msgs = launcher.validate_inputs("Qwen/Qwen2.5-0.5B", "float16", "99999")
    assert ok is False
    assert any("range" in m for m in msgs)

    ok_alpha, _, msgs_alpha = launcher.validate_inputs("Qwen/Qwen2.5-0.5B", "float16", "abc")
    assert ok_alpha is False
    assert any("integer" in m for m in msgs_alpha)


def test_launcher_renders_hardware_card(tmp_path: Path):
    launcher = APEXLauncher(workspace_path=tmp_path)
    html_out = launcher._render_hardware_html()
    assert "Detected Hardware & Runtime" in html_out
    assert launcher.hardware_info["runtime_name"] in html_out
    assert launcher.hardware_info["gpu_name"] in html_out


def test_launcher_checklist_stages(tmp_path: Path):
    launcher = APEXLauncher(workspace_path=tmp_path)
    checklist_html = launcher._render_checklist_html()
    assert len(LAUNCH_STAGES) == 10
    for sid, name in LAUNCH_STAGES:
        assert name in checklist_html


# ── 5. APEXLauncher Launch & Shutdown Pipeline Tests ────────────────────────

def test_launcher_launch_pipeline_mock(tmp_path: Path):
    mock_model_mgr = MagicMock(spec=ModelManager)
    mock_model_mgr.is_loaded = True

    mock_api_mgr = MagicMock()
    mock_api_mgr.config = MagicMock()
    mock_api_mgr.config.internal_port = 8000
    mock_api_mgr.state = MagicMock()
    mock_api_mgr.state.public_url = "https://mock-tunnel.trycloudflare.com"
    mock_api_mgr.state.openai_url = "https://mock-tunnel.trycloudflare.com/v1"
    mock_api_mgr.state.api_key = "APEX_test_secret_key_123"
    mock_api_mgr.state.api_status.value = "running"
    mock_api_mgr.state.api_running = True
    mock_api_mgr.start.return_value = True

    mock_orchestrator = MagicMock()
    mock_orchestrator.state_machine = RuntimeStateMachine()

    launcher = APEXLauncher(
        workspace_path=tmp_path,
        model_manager=mock_model_mgr,
        api_manager=mock_api_mgr,
        orchestrator=mock_orchestrator,
    )
    launcher.config.model_id = "Qwen/Qwen2.5-0.5B"

    progress_events = []
    completion = []

    def _on_prog(sid, st, msg):
        progress_events.append((sid, st, msg))

    def _on_done(success, err):
        completion.append((success, err))

    started = launcher.launch(on_progress=_on_prog, on_complete=_on_done)
    assert started is True

    # Wait for background thread
    for _ in range(60):
        if len(completion) > 0:
            break
        time.sleep(0.05)

    assert len(completion) == 1
    success, err = completion[0]
    assert success is True
    assert err is None
    assert launcher.is_running is True

    # Verify connection panel HTML contains real credentials
    panel_html = launcher._render_connection_panel_html()
    assert "https://mock-tunnel.trycloudflare.com" in panel_html
    assert "Open APEX Chat" in panel_html
    assert "https://mock-tunnel.trycloudflare.com/v1" in panel_html
    assert "Qwen/Qwen2.5-0.5B" in panel_html

    # Test reveal key
    assert launcher._get_active_api_key() == "APEX_test_secret_key_123"

    # Now test shutdown
    shutdown_done = []
    launcher.shutdown(on_complete=lambda ok, e: shutdown_done.append((ok, e)))

    for _ in range(40):
        if len(shutdown_done) > 0:
            break
        time.sleep(0.05)

    assert len(shutdown_done) == 1
    assert shutdown_done[0][0] is True
    assert launcher.is_running is False
    mock_api_mgr.stop.assert_called_once()
    mock_model_mgr.unload_model.assert_called_once()


def test_launcher_duplicate_launch_prevention(tmp_path: Path):
    launcher = APEXLauncher(workspace_path=tmp_path)
    launcher.is_launching = True
    started = launcher.launch()
    assert started is False


def test_launcher_headless_mode(tmp_path: Path):
    launcher = APEXLauncher(workspace_path=tmp_path)
    res1 = launcher.render()
    assert "Headless" in str(res1) or hasattr(res1, "children")

    res2 = launcher.render_shutdown()
    assert "Headless" in str(res2) or hasattr(res2, "children")


# ── 6. Notebook JSON File Structure Tests ───────────────────────────────────

def test_redesigned_notebook_structure():
    nb_path = Path("notebook/APEX.ipynb")
    assert nb_path.exists(), "APEX.ipynb must exist"

    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb.get("cells", [])
    assert len(cells) == 5, f"Expected 5 cells, found {len(cells)}"

    # Cell types sequence: markdown, markdown, code, markdown, code
    assert cells[0]["cell_type"] == "markdown"
    assert cells[1]["cell_type"] == "markdown"
    assert cells[2]["cell_type"] == "code"
    assert cells[3]["cell_type"] == "markdown"
    assert cells[4]["cell_type"] == "code"

    c0_text = "".join(cells[0].get("source", []))
    c1_text = "".join(cells[1].get("source", []))
    c2_text = "".join(cells[2].get("source", []))
    c3_text = "".join(cells[3].get("source", []))
    c4_text = "".join(cells[4].get("source", []))

    # Cell 0: Title
    assert "# APEX — AI Model Runtime" in c0_text

    # Cell 1: Section 1 Header
    assert "## Section 1 — Setup & Run APEX" in c1_text

    # Cell 2: Section 1 Code
    assert "from runtime.ui.launcher import APEXLauncher" in c2_text
    assert "launcher = APEXLauncher(workspace_path=target_dir)" in c2_text
    assert "launcher.render()" in c2_text

    # Verify no dangerous git wipe commands in cell 2
    assert "reset --hard" not in c2_text
    assert "clean -fd" not in c2_text

    # Cell 3: Section 2 Header
    assert "## Section 2 — Shutdown APEX" in c3_text

    # Cell 4: Section 2 Code
    assert "launcher.render_shutdown()" in c4_text

    # Entire notebook must have zero reference to old sections
    all_text = " ".join([c0_text, c1_text, c2_text, c3_text, c4_text])
    for s_idx in (0, 3, 4, 5, 6, 7, 8):
        assert f"Section {s_idx}" not in all_text

