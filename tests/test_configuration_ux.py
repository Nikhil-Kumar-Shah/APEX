"""Comprehensive regression tests for APEX Configuration UX & Model Selection."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from runtime.config.profile import CURATED_PRESETS, get_preset, check_hardware_compatibility
from runtime.config.schema import ApexConfig
from runtime.ui.launcher import APEXLauncher, normalize_hf_model_id


def test_curated_presets_are_instruction_tuned():
    """Verify curated presets are instruction-tuned or distilled reasoning models suitable for chat."""
    assert len(CURATED_PRESETS) >= 3
    for p in CURATED_PRESETS:
        assert p.display_name
        assert p.repo_id
        is_chat_model = any(k in p.repo_id.lower() for k in ["instruct", "distill", "chat", "-it"])
        assert is_chat_model, f"{p.repo_id} should be an instruction/reasoning model"
        assert p.parameter_count
        assert p.estimated_vram_gb > 0
        assert p.recommended_precision in ("float16", "bfloat16", "4bit", "8bit")
        assert p.description


def test_preset_lookup_backward_compatibility():
    """Verify get_preset matches both exact ID and base names."""
    p1 = get_preset("Qwen/Qwen2.5-0.5B-Instruct")
    assert p1 is not None
    assert p1.repo_id == "Qwen/Qwen2.5-0.5B-Instruct"

    # Base match should resolve to the instruction-tuned preset
    p2 = get_preset("Qwen/Qwen2.5-0.5B")
    assert p2 is not None
    assert p2.repo_id == "Qwen/Qwen2.5-0.5B-Instruct"


def test_custom_model_url_normalization():
    """Verify Hugging Face URLs are normalized to owner/repo."""
    url1 = "https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct"
    norm1, ok1, err1 = normalize_hf_model_id(url1)
    assert ok1 is True
    assert norm1 == "meta-llama/Llama-3.2-1B-Instruct"

    url2 = "https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3/tree/main"
    norm2, ok2, err2 = normalize_hf_model_id(url2)
    assert ok2 is True
    assert norm2 == "mistralai/Mistral-7B-Instruct-v0.3"


def test_launcher_preset_details_html_rendering():
    """Verify preset card renders parameters, VRAM, and hardware advice."""
    launcher = APEXLauncher()
    preset = CURATED_PRESETS[0]
    html_card = launcher._render_preset_details_html(preset)

    assert preset.display_name in html_card
    assert preset.parameter_count in html_card
    assert f"{preset.estimated_vram_gb:.1f} GB" in html_card
    assert "Recommended Precision" in html_card


def test_hardware_compatibility_detection():
    """Verify check_hardware_compatibility accurately advises on CPU and GPU scenarios."""
    # Ultra-light model on CPU with sufficient RAM
    status, msg = check_hardware_compatibility(
        "Qwen/Qwen2.5-0.5B-Instruct",
        vram_total_gb=0.0,
        cuda_available=False,
        precision="float32",
        ram_available_gb=12.0,
    )
    assert status in ("cpu", "compatible", "notice")

    # Giant model on CPU that exceeds system RAM
    status_oom, msg_oom = check_hardware_compatibility(
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        vram_total_gb=0.0,
        cuda_available=False,
        precision="float16",
        ram_available_gb=8.0,
    )
    assert status_oom == "incompatible"
    assert "exceeds" in msg_oom.lower() or "insufficient" in msg_oom.lower()


def test_launcher_validation_logic():
    """Verify APEXLauncher.validate_inputs checks model format, ports, and hardware fit."""
    launcher = APEXLauncher()

    # 1. Valid inputs
    ok, norm, msgs = launcher.validate_inputs("Qwen/Qwen2.5-0.5B-Instruct", "float16", "8000")
    assert ok is True
    assert norm == "Qwen/Qwen2.5-0.5B-Instruct"

    # 2. Invalid port outside range
    ok_p, _, err_p = launcher.validate_inputs("Qwen/Qwen2.5-0.5B-Instruct", "float16", "80")
    assert ok_p is False
    assert any("allowed range" in m for m in err_p)

    # 3. Invalid model ID syntax
    ok_m, _, err_m = launcher.validate_inputs("///invalid-model-name", "float16", "8000")
    assert ok_m is False


def test_launcher_widgets_initialization_when_ipywidgets_available():
    """Verify ipywidgets vertical configuration structure when ipywidgets is present."""
    try:
        import ipywidgets as widgets
    except ImportError:
        pytest.skip("ipywidgets not installed in current environment")

    launcher = APEXLauncher()
    launcher.render()

    w = launcher._widgets
    assert "model_source_radio" in w
    assert "model_preset" in w
    assert "model_id" in w
    assert "precision" in w
    assert "start_btn" in w
    assert "validate_btn" in w
    assert "dev_console_accordion" in w

    radio = w["model_source_radio"]
    assert "Curated Model Preset" in radio.options
    assert "Custom Hugging Face Model or URL" in radio.options

    prec_dd = w["precision"]
    prec_values = [opt[1] if isinstance(opt, tuple) else opt for opt in prec_dd.options]
    assert "auto" in prec_values
    assert "4bit" in prec_values
    assert "8bit" in prec_values
    assert "float16" in prec_values
    assert "float32" in prec_values
