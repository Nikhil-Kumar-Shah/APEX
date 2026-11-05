"""Comprehensive tests for APEX Notebook Simplification and Native Terminal Output."""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bootstrap.dependency_manager import DependencyInstaller
from runtime.ui.launcher import (
    APEX_BUILD_ID,
    APEXLauncher,
    ScopedOutputRedirect,
    TerminalLoggingHandler,
    detect_environment_hardware,
    redact_sensitive_data,
)


# ── 1. Compact Hardware Summary Tests ─────────────────────────────────────────

def test_compact_hardware_summary_colab_cpu():
    """Verify compact 4-item grid and concise warning in Colab CPU environment."""
    launcher = APEXLauncher()
    launcher.hardware_info = {
        "is_colab": True,
        "runtime_name": "Google Colab",
        "device": "cpu",
        "gpu_name": "None (CPU Mode)",
        "vram_total_gb": 0.0,
        "ram_total_gb": 12.67,
        "cuda_available": False,
        "drive_mounted": False,
    }

    html_out = launcher._render_hardware_html()
    assert "Google Colab" in html_out
    assert "None (CPU Mode)" in html_out
    assert "12.67 GB" in html_out
    assert "Colab CPU Runtime Active" in html_out
    assert "Storage Notice" in html_out
    assert "apex-build-badge" in html_out


def test_compact_hardware_summary_cuda_gpu():
    """Verify GPU specifications rendered without CPU warnings when CUDA is available."""
    launcher = APEXLauncher()
    launcher.hardware_info = {
        "is_colab": True,
        "runtime_name": "Google Colab",
        "device": "cuda:0",
        "gpu_name": "Tesla T4",
        "vram_total_gb": 15.0,
        "ram_total_gb": 12.67,
        "cuda_available": True,
        "drive_mounted": True,
    }

    html_out = launcher._render_hardware_html()
    assert "Tesla T4" in html_out
    assert "15.0 GB VRAM" in html_out
    assert "Colab CPU Runtime Active" not in html_out
    assert "CPU Mode Active" not in html_out
    assert "Storage Notice" not in html_out


# ── 2. Terminal Redirection & Scoped Output Capture ───────────────────────────

def test_scoped_output_redirect_restores_globals():
    """Verify ScopedOutputRedirect intercepts stdout/stderr and cleanly restores originals."""
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr

    launcher = APEXLauncher()
    received_lines = []
    launcher.write_terminal = lambda text: received_lines.append(text)

    with ScopedOutputRedirect(launcher):
        assert sys.stdout != orig_stdout
        assert sys.stderr != orig_stderr

        # Test stdout
        print("Hello from print statement!")
        # Test stderr
        sys.stderr.write("Test error output\n")

    # Verify original streams restored
    assert sys.stdout == orig_stdout
    assert sys.stderr == orig_stderr

    # Verify intercepted output
    assert any("Hello from print statement!" in l for l in received_lines)
    assert any("Test error output" in l for l in received_lines)


def test_terminal_logging_handler_formatting():
    """Verify TerminalLoggingHandler formats records cleanly with level tags."""
    launcher = APEXLauncher()
    captured = []
    launcher.write_terminal = lambda text: captured.append(text)

    handler = TerminalLoggingHandler(launcher)
    logger = logging.getLogger("apex_test_logger")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False

    try:
        logger.info("Informational message")
        logger.warning("Warning message")
        logger.error("Error occurred")

        try:
            raise ValueError("Test traceback exception")
        except ValueError:
            logger.exception("Failed with exception")

        assert any("INFO: Informational message" in c for c in captured)
        assert any("WARNING: Warning message" in c for c in captured)
        assert any("ERROR: Error occurred" in c for c in captured)
        assert any("Test traceback exception" in c for c in captured)
    finally:
        logger.removeHandler(handler)


# ── 3. Sensitive Data Redaction Tests ─────────────────────────────────────────

def test_sensitive_data_redaction_in_terminal():
    """Verify Hugging Face tokens and API keys are redacted before terminal display."""
    raw_text = (
        "Fetching model with token hf_AbCdEf1234567890abcdef1234567890\n"
        "Active server key: apex_sk_secret_1234567890abcdef1234567890\n"
        "Authorization: Bearer sk-proj-1234567890abcdef1234567890"
    )
    redacted = redact_sensitive_data(raw_text)

    assert "hf_AbCdEf" not in redacted
    assert "[REDACTED_HF_TOKEN]" in redacted or "[REDACTED" in redacted
    assert "apex_sk_secret" not in redacted
    assert "sk-proj-1234567890" not in redacted


def test_write_terminal_redacts_automatically():
    """Verify launcher.write_terminal applies redaction before passing to terminal widget."""
    launcher = APEXLauncher()
    mock_terminal = MagicMock()
    launcher._terminal_output = mock_terminal

    launcher.write_terminal("Using Hugging Face token hf_1234567890abcdef1234567890abcdef12")

    mock_terminal.append_stdout.assert_called_once()
    appended_str = mock_terminal.append_stdout.call_args[0][0]
    assert "hf_1234567890" not in appended_str
    assert "[REDACTED" in appended_str


# ── 4. Terminal Non-Destructive Clear Tests ───────────────────────────────────

def test_clear_terminal_invokes_widget_clear():
    """Verify clear_terminal and clear_shutdown_terminal invoke clear_output()."""
    launcher = APEXLauncher()
    mock_term1 = MagicMock()
    mock_term2 = MagicMock()
    launcher._terminal_output = mock_term1
    launcher._shutdown_terminal_output = mock_term2

    launcher.clear_terminal()
    mock_term1.clear_output.assert_called_once()

    launcher.clear_shutdown_terminal()
    mock_term2.clear_output.assert_called_once()


# ── 5. Dependency Manager Subprocess Line Streaming Tests ──────────────────────

def test_dependency_manager_streams_realtime_pip_output(tmp_path: Path):
    """Verify DependencyInstaller pipes subprocess stdout line-by-line to logger."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("pytest\n", encoding="utf-8")

    installer = DependencyInstaller(req_file)

    mock_proc = MagicMock()
    mock_proc.stdout = ["Collecting pytest\n", "Downloading pytest-8.0.0.whl\n", "Successfully installed pytest\n"]
    mock_proc.returncode = 0

    logged_lines = []
    test_logger = logging.getLogger("bootstrap.dependency")
    
    class TestHandler(logging.Handler):
        def emit(self, record):
            logged_lines.append(record.getMessage())

    th = TestHandler()
    test_logger.addHandler(th)

    try:
        with patch("subprocess.Popen", return_value=mock_proc):
            ok = installer.install(["pytest"])
            assert ok is True
            assert any("pip: Collecting pytest" in l for l in logged_lines)
            assert any("pip: Successfully installed pytest" in l for l in logged_lines)
    finally:
        test_logger.removeHandler(th)


# ── 6. UI Structure & Widgets Initialization Tests ─────────────────────────────

def test_launcher_section_1_and_2_widgets_structure():
    """Verify widgets dictionary includes all required Section 1 and Section 2 controls."""
    try:
        import ipywidgets as widgets
    except ImportError:
        pytest.skip("ipywidgets not installed in local environment")

    launcher = APEXLauncher()
    launcher.render()

    w = launcher._widgets
    assert "start_btn" in w
    assert "terminal_output" in w
    assert "clear_terminal_btn" in w
    assert "model_source_radio" in w
    assert "model_preset" in w
    assert "model_id" in w
    assert "precision" in w
    assert "hf_token" in w

    launcher.render_shutdown()
    sw = launcher._shutdown_widgets
    assert "stop_btn" in sw
    assert "status_html" in sw
    assert "terminal_output" in sw
    assert "clear_terminal_btn" in sw


# ── 7. Notebook 5-Cell Layout Verification ─────────────────────────────────────

def test_notebook_exact_two_sections():
    """Verify notebook contains exactly 5 cells representing Section 1 and Section 2."""
    nb_path = Path("notebook/APEX.ipynb")
    assert nb_path.exists()

    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb.get("cells", [])
    assert len(cells) == 5

    c1_text = "".join(cells[1].get("source", []))
    c2_text = "".join(cells[2].get("source", []))
    c3_text = "".join(cells[3].get("source", []))
    c4_text = "".join(cells[4].get("source", []))

    assert "## Section 1 — Setup & Run APEX" in c1_text
    assert "launcher.render()" in c2_text
    assert "## Section 2 — Shutdown APEX" in c3_text
    assert "launcher.render_shutdown()" in c4_text
