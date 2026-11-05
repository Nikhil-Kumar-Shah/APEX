"""Model Profile system for APEX — V1 (Transformers-only defaults)."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ModelProfile:
    """Contains capabilities, limits, and configurations for a specific model family."""

    name: str
    preferred_engine: str  # V1: always 'transformers'
    context_limit: int
    default_parameters: Dict[str, Any] = field(default_factory=dict)
    streaming_supported: bool = True
    recommended_gpu_utilization: float = 0.85
    precision_supported: List[str] = field(default_factory=lambda: ["float16", "bfloat16"])


@dataclass
class ModelPreset:
    """Curated model preset metadata for quick user selection."""

    repo_id: str
    display_name: str
    family: str
    description: str
    estimated_vram_gb: float
    parameter_count: str
    recommended_precision: str = "float16"
    requires_auth: bool = False


# Curated presets optimized for Google Colab GPU tiers (T4, V100, A100) and CPU
CURATED_PRESETS: List[ModelPreset] = [
    ModelPreset(
        repo_id="Qwen/Qwen2.5-0.5B",
        display_name="Qwen 2.5 0.5B (Ultra-Lightweight)",
        family="qwen",
        description="Ultra-compact 0.5B model (~1.2 GB VRAM). Optimal for fast prototyping, Colab T4, and CPU.",
        estimated_vram_gb=1.2,
        parameter_count="0.5B",
        recommended_precision="float16",
        requires_auth=False,
    ),
    ModelPreset(
        repo_id="Qwen/Qwen2.5-1.5B",
        display_name="Qwen 2.5 1.5B (Fast & Balanced)",
        family="qwen",
        description="Balanced 1.5B model (~3.5 GB VRAM). Great balance of reasoning, speed, and low memory.",
        estimated_vram_gb=3.5,
        parameter_count="1.5B",
        recommended_precision="float16",
        requires_auth=False,
    ),
    ModelPreset(
        repo_id="deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        display_name="DeepSeek R1 Distill 1.5B (Reasoning)",
        family="deepseek",
        description="Distilled reasoning model (~3.5 GB VRAM). Exceptional logic, math, and code solving.",
        estimated_vram_gb=3.5,
        parameter_count="1.5B",
        recommended_precision="float16",
        requires_auth=False,
    ),
    ModelPreset(
        repo_id="google/gemma-2-2b-it",
        display_name="Gemma 2 2B IT (Google High Efficiency)",
        family="gemma",
        description="Instruction-tuned 2B model (~5.0 GB VRAM). Modern high-efficiency architecture by Google.",
        estimated_vram_gb=5.0,
        parameter_count="2B",
        recommended_precision="float16",
        requires_auth=False,
    ),
    ModelPreset(
        repo_id="Qwen/Qwen2.5-7B",
        display_name="Qwen 2.5 7B (High Quality)",
        family="qwen",
        description="Powerful 7B model (~14.0 GB VRAM). Maximum quality for Colab T4 (15GB) or high-RAM GPUs.",
        estimated_vram_gb=14.0,
        parameter_count="7B",
        recommended_precision="float16",
        requires_auth=False,
    ),
    ModelPreset(
        repo_id="meta-llama/Llama-3.2-1B-Instruct",
        display_name="Llama 3.2 1B Instruct (Meta Gated)",
        family="meta-llama",
        description="Meta 1B instruction model (~2.5 GB VRAM). Requires Hugging Face Access Token with granted access.",
        estimated_vram_gb=2.5,
        parameter_count="1B",
        recommended_precision="float16",
        requires_auth=True,
    ),
]


# Preset profiles for widely used open-source model families
# V1: All profiles use 'transformers' as the preferred engine
MODEL_PROFILES: Dict[str, ModelProfile] = {
    "qwen": ModelProfile(
        name="Qwen",
        preferred_engine="transformers",
        context_limit=32768,
        default_parameters={"temperature": 0.7, "top_p": 0.8, "repetition_penalty": 1.1},
        recommended_gpu_utilization=0.90,
    ),
    "deepseek": ModelProfile(
        name="DeepSeek",
        preferred_engine="transformers",
        context_limit=16384,
        default_parameters={"temperature": 0.6, "top_p": 0.95, "repetition_penalty": 1.0},
        recommended_gpu_utilization=0.90,
    ),
    "deepseek-ai": ModelProfile(
        name="DeepSeek",
        preferred_engine="transformers",
        context_limit=16384,
        default_parameters={"temperature": 0.6, "top_p": 0.95, "repetition_penalty": 1.0},
        recommended_gpu_utilization=0.90,
    ),
    "google": ModelProfile(
        name="Google",
        preferred_engine="transformers",
        context_limit=8192,
        default_parameters={"temperature": 0.7, "top_p": 0.9, "repetition_penalty": 1.0},
        recommended_gpu_utilization=0.80,
    ),
    "gemma": ModelProfile(
        name="Gemma",
        preferred_engine="transformers",
        context_limit=8192,
        default_parameters={"temperature": 0.7, "top_p": 0.9, "repetition_penalty": 1.0},
        recommended_gpu_utilization=0.80,
    ),
    "mistralai": ModelProfile(
        name="Mistral",
        preferred_engine="transformers",
        context_limit=32768,
        default_parameters={"temperature": 0.7, "top_p": 0.9, "repetition_penalty": 1.0},
        recommended_gpu_utilization=0.85,
    ),
    "meta-llama": ModelProfile(
        name="Llama",
        preferred_engine="transformers",
        context_limit=8192,
        default_parameters={"temperature": 0.7, "top_p": 0.9, "repetition_penalty": 1.0},
        recommended_gpu_utilization=0.85,
    ),
    "custom": ModelProfile(
        name="Custom",
        preferred_engine="transformers",
        context_limit=2048,
        default_parameters={"temperature": 0.7, "top_p": 0.9},
        recommended_gpu_utilization=0.85,
    ),
}


def get_profile(family_name: str) -> ModelProfile:
    """Retrieves the model profile for a given family.

    Falls back to 'custom' if the family is not recognized.

    Args:
        family_name: The name of the model family (typically the org from a HF repo ID).

    Returns:
        ModelProfile: The matched profile.
    """
    key = family_name.lower().strip()
    return MODEL_PROFILES.get(key, MODEL_PROFILES["custom"])


def get_preset(repo_id: str) -> Optional[ModelPreset]:
    """Retrieves a curated preset by exact repository identifier."""
    repo_lower = repo_id.strip().lower()
    for preset in CURATED_PRESETS:
        if preset.repo_id.lower() == repo_lower:
            return preset
    return None


def estimate_vram(repo_id: str, precision: str = "float16") -> float:
    """Estimates the approximate VRAM required for a model in gigabytes."""
    preset = get_preset(repo_id)
    base_vram = preset.estimated_vram_gb if preset else 4.0

    # Adjust for precision
    if precision == "float32":
        return base_vram * 2.0
    elif precision in ("float16", "bfloat16"):
        return base_vram
    elif precision in ("int8", "8bit"):
        return base_vram * 0.55
    elif precision in ("int4", "4bit"):
        return base_vram * 0.35
    return base_vram


def check_hardware_compatibility(
    repo_id: str,
    vram_total_gb: float,
    cuda_available: bool,
    precision: str = "float16"
) -> Tuple[str, str]:
    """Evaluates whether the selected model fits the detected hardware.

    Returns:
        Tuple[str, str]: Status key ('compatible', 'tight', 'warning', 'cpu') and explanation.
    """
    if not cuda_available:
        return (
            "cpu",
            "No GPU detected. Model will execute on CPU (slower generation, ensure sufficient system RAM)."
        )

    required_vram = estimate_vram(repo_id, precision)

    if vram_total_gb >= (required_vram + 1.0):
        return (
            "compatible",
            f"Compatible. Required ~{required_vram:.1f} GB VRAM fits comfortably in available {vram_total_gb:.1f} GB."
        )
    elif vram_total_gb >= required_vram:
        return (
            "tight",
            f"Tight VRAM. Required ~{required_vram:.1f} GB is close to total {vram_total_gb:.1f} GB. Keep batch size at 1."
        )
    else:
        return (
            "warning",
            f"Potential OOM. Model requires ~{required_vram:.1f} GB VRAM, but device only has {vram_total_gb:.1f} GB. Consider a smaller model."
        )
