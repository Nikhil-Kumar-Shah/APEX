"""Model Profile system for APEX — V1 (Transformers-only defaults)."""


from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
