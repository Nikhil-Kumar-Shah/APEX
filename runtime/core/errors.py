"""Structured error classification system for APEX."""

from typing import Any, Dict, Optional


class RuntimeErrorBase(Exception):
    """Base exception for all APEX errors.


    Provides a clean, formatted diagnostic message containing probable causes
    and recovery suggestions instead of raw stack trace text.
    """

    def __init__(
        self,
        message: str,
        cause: str,
        recovery: str,
        log_info: Optional[Dict[str, Any]] = None,
    ):
        """Initializes the base runtime exception.

        Args:
            message: Clean explanation of the error.
            cause: Probable cause.
            recovery: Suggested recovery steps.
            log_info: Key-value log details for diagnostics.
        """
        super().__init__(message)
        self.message = message
        self.cause = cause
        self.recovery = recovery
        self.log_info = log_info or {}

    def __str__(self) -> str:
        border = "-" * 60
        details = "\n".join(f"  {k}: {v}" for k, v in self.log_info.items())
        details_block = f"\n[Diagnostic Details]:\n{details}" if details else ""

        return (
            f"\n{border}\n"
            f"[Error]: {self.message}\n"
            f"[Probable Cause]: {self.cause}\n"
            f"[Suggested Action]: {self.recovery}"
            f"{details_block}\n"
            f"{border}"
        )


class ModelNotFoundError(RuntimeErrorBase):
    """Raised when a requested model cannot be located locally or in Hugging Face Hub."""

    def __init__(self, model_id: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Model not found: '{model_id}'",
            cause="The specified model ID does not exist in local cache and could not be retrieved from Hugging Face Hub.",
            recovery="Double-check the model ID spelling, verify repository visibility, or log in if the model is private.",
            log_info=log_info,
        )


class EngineUnavailableError(RuntimeErrorBase):
    """Raised when an inference engine cannot be loaded or is not installed."""

    def __init__(self, engine_name: str, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Inference engine '{engine_name}' is unavailable.",
            cause=f"Required libraries for '{engine_name}' are missing or incompatible: {details}",
            recovery=f"Install the engine using `pip install {engine_name}` or select an alternative engine (e.g. transformers) in config.",
            log_info=log_info,
        )


class DownloadFailedError(RuntimeErrorBase):
    """Raised when model file downloading fails."""

    def __init__(self, model_id: str, reason: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Download failed for model '{model_id}'",
            cause=f"Network disruption, timeout, or missing files: {reason}",
            recovery="Ensure a stable internet connection, check Hugging Face status, or retry downloading.",
            log_info=log_info,
        )


class AuthenticationFailedError(RuntimeErrorBase):
    """Raised when Hugging Face hub authentication fails."""

    def __init__(self, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message="Hugging Face authentication failed.",
            cause="Invalid HF token, expired token, or insufficient read permissions for a private repository.",
            recovery="Obtain a valid User Access Token (Read/Write) from huggingface.co and update your HF_TOKEN config or environment variable.",
            log_info=log_info,
        )


class UnsupportedArchitectureError(RuntimeErrorBase):
    """Raised when model architecture cannot be loaded by the chosen engine."""

    def __init__(self, model_id: str, engine_name: str, arch: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Architecture '{arch}' of model '{model_id}' is unsupported by engine '{engine_name}'.",
            cause="The selected engine adapter does not implement support for this model architecture.",
            recovery="Choose an alternative engine (e.g., 'transformers') or use a model with a supported architecture.",
            log_info=log_info,
        )


class UnsupportedQuantizationError(RuntimeErrorBase):
    """Raised when quantization is invalid or unsupported."""

    def __init__(self, quant_type: str, engine_name: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Quantization type '{quant_type}' is unsupported by engine '{engine_name}'.",
            cause="The specified engine version does not support compiling or running this quantization format.",
            recovery="Choose a compatible format (e.g. GGUF for llama.cpp, AWQ/GPTQ for vLLM, or unquantized 16-bit precision).",
            log_info=log_info,
        )


class GPUOutOfMemoryError(RuntimeErrorBase):
    """Raised when memory allocation fails due to insufficient VRAM."""

    def __init__(self, requested_bytes: Optional[int] = None, log_info: Optional[Dict[str, Any]] = None):
        req_str = f" of {requested_bytes} bytes" if requested_bytes else ""
        super().__init__(
            message=f"Out of GPU Memory (OOM) during allocation{req_str}.",
            cause="The GPU does not have enough free memory (VRAM) to load this model, batch size, or context limit.",
            recovery="Enable quantization, reduce the context length, set `gpu_memory_utilization` lower, or upgrade the GPU runtime (e.g. to A100/L4 in Colab Pro).",
            log_info=log_info,
        )


class CacheCorruptedError(RuntimeErrorBase):
    """Raised when cached model files fail integrity verification."""

    def __init__(self, cache_path: str, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Model cache corruption detected at: '{cache_path}'",
            cause=f"Model files failed sha256 checksum or size verification. Details: {details}",
            recovery="Clear the cached files for this model and redownload.",
            log_info=log_info,
        )


class InvalidConfigurationError(RuntimeErrorBase):
    """Raised when configuration values are incompatible."""

    def __init__(self, key: str, value: Any, reason: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Invalid configuration parameter: '{key}' = {value}",
            cause=f"Validation constraints failed: {reason}",
            recovery="Adjust config value according to the documentation schemas.",
            log_info=log_info,
        )


class StreamingFailureError(RuntimeErrorBase):
    """Raised when streaming generation fails mid-stream."""

    def __init__(self, model_id: str, reason: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Streaming generation failure on model '{model_id}'",
            cause=f"The underlying engine adapter encountered an internal error during iteration: {reason}",
            recovery="Restart the inference engine runtime session or clear context.",
            log_info=log_info,
        )
