"""Performance Modes and profile translation system."""

from typing import Any, Dict, Optional


class PerformanceModeManager:
    """Translates high-level performance preferences into engine-specific arguments."""

    MODES: Dict[str, Dict[str, Any]] = {
        "fast": {
            "gpu_memory_utilization": 0.70,
            "context_limit": 2048,
            "precision": "float16",
            "quantization": "awq",  # prioritizes fast quantized model weights
        },
        "balanced": {
            "gpu_memory_utilization": 0.85,
            "context_limit": 4096,
            "precision": "float16",
            "quantization": "none",
        },
        "quality": {
            "gpu_memory_utilization": 0.95,
            "context_limit": 8192,
            "precision": "bfloat16",
            "quantization": "none",
        },
        "custom": {
            "gpu_memory_utilization": 0.85,
            "context_limit": 2048,
            "precision": "float16",
            "quantization": "none",
        },
    }

    @classmethod
    def get_settings(cls, mode_name: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Resolves config values for a given performance mode.

        Args:
            mode_name: Name of the mode ('fast', 'balanced', 'quality', 'custom').
            overrides: Custom dictionary overriding default parameters.

        Returns:
            Dict[str, Any]: Consolidated engine config settings.
        """
        key = mode_name.lower().strip()
        settings = cls.MODES.get(key, cls.MODES["balanced"]).copy()
        if overrides:
            settings.update(overrides)
        return settings
