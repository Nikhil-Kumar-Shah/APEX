"""Model Profile system for APEX — V1 (Transformers-only defaults)."""

import re
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
        repo_id="Qwen/Qwen2.5-0.5B-Instruct",
        display_name="Qwen 2.5 0.5B Instruct (Ultra-Lightweight)",
        family="qwen",
        description="Instruction-tuned 0.5B model (~1.2 GB VRAM). Optimal for fast prototyping, Colab T4, and CPU.",
        estimated_vram_gb=1.2,
        parameter_count="0.5B",
        recommended_precision="float16",
        requires_auth=False,
    ),
    ModelPreset(
        repo_id="Qwen/Qwen2.5-1.5B-Instruct",
        display_name="Qwen 2.5 1.5B Instruct (Fast & Balanced)",
        family="qwen",
        description="Instruction-tuned 1.5B model (~3.5 GB VRAM). Great balance of reasoning, speed, and low memory.",
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
        repo_id="Qwen/Qwen2.5-7B-Instruct",
        display_name="Qwen 2.5 7B Instruct (High Quality)",
        family="qwen",
        description="Instruction-tuned 7B model (~14.0 GB VRAM). Maximum quality for Colab T4 (15GB) or high-RAM GPUs.",
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
    """Retrieves a curated preset by exact repository identifier or normalized match."""
    if not repo_id:
        return None
    repo_lower = repo_id.strip().lower()
    for preset in CURATED_PRESETS:
        if preset.repo_id.lower() == repo_lower:
            return preset
        # Also allow matching without -Instruct for backward compatibility
        if preset.repo_id.lower().replace("-instruct", "") == repo_lower.replace("-instruct", ""):
            return preset
    return None


def estimate_vram(repo_id: str, precision: str = "float16") -> float:
    """Estimates the approximate VRAM required for a model in gigabytes."""
    preset = get_preset(repo_id)
    if preset:
        base_vram = preset.estimated_vram_gb
    else:
        # Try parsing parameter count from model ID (e.g. 70b, 14b, 7b, 3b, 1.5b, 0.5b)
        repo_lower = repo_id.lower()
        match = re.search(r"(\d+(?:\.\d+)?)\s*b\b", repo_lower)
        if match:
            param_billions = float(match.group(1))
            # Approximately 2 GB per billion parameters in float16
            base_vram = param_billions * 2.0
        else:
            base_vram = 4.0

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
    precision: str = "float16",
    ram_available_gb: Optional[float] = None,
) -> Tuple[str, str]:
    """Evaluates whether the selected model fits the detected hardware.

    Returns:
        Tuple[str, str]: Status key ('compatible', 'tight', 'warning', 'cpu', 'incompatible') and explanation.
    """
    if not cuda_available:
        required_ram = estimate_vram(repo_id, precision) * 1.2
        if ram_available_gb is not None and ram_available_gb > 0:
            if required_ram > ram_available_gb:
                return (
                    "incompatible",
                    (
                        f"Model requires ~{required_ram:.1f} GB RAM, which exceeds available system RAM "
                        f"({ram_available_gb:.1f} GB). Loading will cause the runtime to crash with Out-Of-Memory. "
                        "Please select a smaller model (≤ 1.5B parameters) or enable a GPU in Colab via "
                        "Runtime → Change runtime type → T4 GPU."
                    ),
                )
            elif required_ram > (ram_available_gb * 0.75):
                return (
                    "tight",
                    (
                        f"Model requires ~{required_ram:.1f} GB RAM, which is close to available system RAM "
                        f"({ram_available_gb:.1f} GB). Generation on CPU will be slow and memory is tight."
                    ),
                )
            else:
                return (
                    "cpu",
                    (
                        f"CPU mode active. Estimated RAM usage: ~{required_ram:.1f} GB of {ram_available_gb:.1f} GB available. "
                        "Note: CPU generation will be significantly slower than GPU acceleration."
                    ),
                )
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


# ── URL Normalization & Validation ───────────────────────────────────────────

HF_URL_PATTERN = re.compile(
    r"^https?://(?:www\.)?huggingface\.co/([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)(?:/.*)?$",
    re.IGNORECASE,
)
HF_REPO_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9._-]+/)?[a-zA-Z0-9._-]+$"
)


def normalize_hf_model_id(val: str) -> Tuple[str, bool, Optional[str]]:
    """Normalizes and validates a Hugging Face model identifier or URL.

    Accepts:
        - Full HF URL: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct
        - HF URL with tree/branch: https://huggingface.co/meta-llama/Llama-3.2-1B/tree/main
        - HF URL with .git: https://huggingface.co/org/model.git
        - Standard repo ID: Qwen/Qwen2.5-1.5B-Instruct
        - Single-part repo ID: gpt2

    Returns:
        (normalized_model_id, is_valid, error_message_or_none)
    """
    if not val or not isinstance(val, str):
        return ("", False, "Model ID is required.")

    cleaned = val.strip()
    if not cleaned:
        return ("", False, "Model ID cannot be empty.")

    # Check for dangerous schemes
    lower = cleaned.lower()
    for scheme in ("javascript:", "file:", "data:", "ftp:", "vbscript:"):
        if lower.startswith(scheme):
            return ("", False, f"Invalid model URL scheme '{scheme}'.")

    # If it is a web URL, it must be huggingface.co
    if lower.startswith("http://") or lower.startswith("https://"):
        match = HF_URL_PATTERN.match(cleaned)
        if match:
            repo_id = match.group(1)
            if repo_id.endswith(".git"):
                repo_id = repo_id[:-4]
            return (repo_id, True, None)
        else:
            return (
                cleaned,
                False,
                "URL must be a valid Hugging Face repository URL (e.g. https://huggingface.co/org/model).",
            )

    # Clean potential trailing .git or slashes from raw repo ID
    repo_cleaned = cleaned.rstrip("/")
    if repo_cleaned.endswith(".git"):
        repo_cleaned = repo_cleaned[:-4]

    # Validate repo ID pattern
    if HF_REPO_PATTERN.match(repo_cleaned):
        return (repo_cleaned, True, None)

    return (
        cleaned,
        False,
        "Invalid model ID format. Use format 'organization/model-name' or 'model-name'.",
    )


# ── Hardware Detection ───────────────────────────────────────────────────────

def detect_environment_hardware() -> Dict[str, Any]:
    """Detects real hardware accelerator, memory, and environment details."""
    import os
    import sys
    from pathlib import Path

    is_colab = "google.colab" in sys.modules or os.environ.get("COLAB_GPU") is not None
    env_name = "Google Colab" if is_colab else "Local Environment"

    device = "cpu"
    gpu_name = "None (CPU Mode)"
    vram_total_gb: Optional[float] = None
    vram_free_gb: Optional[float] = None
    cuda_available = False

    # Check PyTorch CUDA / MPS
    try:
        import torch

        if torch.cuda.is_available():
            cuda_available = True
            device = "cuda:0"
            gpu_name = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            vram_total_gb = round(props.total_memory / (1024**3), 2)
            try:
                free_bytes, _ = torch.cuda.mem_get_info(0)
                vram_free_gb = round(free_bytes / (1024**3), 2)
            except Exception:
                vram_free_gb = vram_total_gb
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
            gpu_name = "Apple Silicon (MPS)"
    except ImportError:
        pass

    # System RAM
    ram_total_gb = 0.0
    ram_avail_gb = 0.0
    try:
        import psutil

        mem = psutil.virtual_memory()
        ram_total_gb = round(mem.total / (1024**3), 2)
        ram_avail_gb = round(mem.available / (1024**3), 2)
    except Exception:
        ram_total_gb = 8.0
        ram_avail_gb = 4.0

    # Storage environment
    storage_desc = "Local Storage Disk"
    drive_mounted = False
    if is_colab:
        drive_path = Path("/content/drive/MyDrive")
        if drive_path.exists():
            drive_mounted = True
            storage_desc = "Google Drive (Persistent)"
        else:
            storage_desc = "Ephemeral VM Disk (Non-Persistent)"
    else:
        storage_desc = "Local Workspace Disk"

    return {
        "is_colab": is_colab,
        "runtime_name": env_name,
        "device": device,
        "gpu_name": gpu_name,
        "vram_total_gb": vram_total_gb,
        "vram_free_gb": vram_free_gb,
        "ram_total_gb": ram_total_gb,
        "ram_available_gb": ram_avail_gb,
        "cuda_available": cuda_available,
        "python_version": sys.version.split()[0],
        "drive_mounted": drive_mounted,
        "storage_desc": storage_desc,
    }
