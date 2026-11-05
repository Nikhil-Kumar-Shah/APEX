"""Structured error classification system for APEX with standard diagnostic codes."""

from typing import Any, Dict, Optional


class ApexErrorCode:
    """Standardized APEX Error Codes."""
    GPU_NOT_AVAILABLE = "APEX-E001"
    DEPENDENCY_INSTALLATION_FAILED = "APEX-E002"
    MODEL_DOWNLOAD_FAILED = "APEX-E003"
    MODEL_FILES_INVALID = "APEX-E004"
    MODEL_LOAD_FAILED = "APEX-E005"
    CUDA_OUT_OF_MEMORY = "APEX-E006"
    API_STARTUP_FAILED = "APEX-E007"
    API_HEALTH_CHECK_FAILED = "APEX-E008"
    CLOUDFLARED_NOT_FOUND = "APEX-E009"
    TUNNEL_STARTUP_FAILED = "APEX-E010"
    TUNNEL_URL_NOT_FOUND = "APEX-E011"
    PUBLIC_ENDPOINT_UNAVAILABLE = "APEX-E012"
    PUBLIC_INFERENCE_FAILED = "APEX-E013"
    GENERAL_RUNTIME_ERROR = "APEX-E000"


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
        code: Optional[str] = None,
    ):
        """Initializes the base runtime exception.

        Args:
            message: Clean explanation of the error.
            cause: Probable cause.
            recovery: Suggested recovery steps.
            log_info: Key-value log details for diagnostics.
            code: Standard APEX error code (e.g. 'APEX-E001').
        """
        super().__init__(message)
        self.message = message
        self.cause = cause
        self.recovery = recovery
        self.log_info = log_info or {}
        self.code = code or ApexErrorCode.GENERAL_RUNTIME_ERROR

    def __str__(self) -> str:
        border = "-" * 60
        details = "\n".join(f"  {k}: {v}" for k, v in self.log_info.items())
        details_block = f"\n[Diagnostic Details]:\n{details}" if details else ""
        code_str = f" [{self.code}]" if self.code else ""

        return (
            f"\n{border}\n"
            f"[Error]{code_str}: {self.message}\n"
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
            code=ApexErrorCode.MODEL_DOWNLOAD_FAILED,
        )


class EngineUnavailableError(RuntimeErrorBase):
    """Raised when an inference engine cannot be loaded or is not installed."""

    def __init__(self, engine_name: str, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Inference engine '{engine_name}' is unavailable.",
            cause=f"Required libraries for '{engine_name}' are missing or incompatible: {details}",
            recovery=f"Install the engine using `pip install {engine_name}` or select an alternative engine (e.g. transformers) in config.",
            log_info=log_info,
            code=ApexErrorCode.MODEL_LOAD_FAILED,
        )


class DownloadFailedError(RuntimeErrorBase):
    """Raised when model file downloading fails."""

    def __init__(self, model_id: str, reason: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Download failed for model '{model_id}'",
            cause=f"Network disruption, timeout, or missing files: {reason}",
            recovery="Ensure a stable internet connection, check Hugging Face status, or retry downloading.",
            log_info=log_info,
            code=ApexErrorCode.MODEL_DOWNLOAD_FAILED,
        )


class AuthenticationFailedError(RuntimeErrorBase):
    """Raised when Hugging Face hub authentication fails."""

    def __init__(self, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message="Hugging Face authentication failed.",
            cause="Invalid HF token, expired token, or insufficient read permissions for a private repository.",
            recovery="Obtain a valid User Access Token (Read/Write) from huggingface.co and update your HF_TOKEN config or environment variable.",
            log_info=log_info,
            code=ApexErrorCode.MODEL_DOWNLOAD_FAILED,
        )


class UnsupportedArchitectureError(RuntimeErrorBase):
    """Raised when model architecture cannot be loaded by the chosen engine."""

    def __init__(self, model_id: str, engine_name: str, arch: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Architecture '{arch}' of model '{model_id}' is unsupported by engine '{engine_name}'.",
            cause="The selected engine adapter does not implement support for this model architecture.",
            recovery="Choose an alternative engine (e.g., 'transformers') or use a model with a supported architecture.",
            log_info=log_info,
            code=ApexErrorCode.MODEL_LOAD_FAILED,
        )


class UnsupportedQuantizationError(RuntimeErrorBase):
    """Raised when quantization is invalid or unsupported."""

    def __init__(self, quant_type: str, engine_name: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Quantization type '{quant_type}' is unsupported by engine '{engine_name}'.",
            cause="The specified engine version does not support compiling or running this quantization format.",
            recovery="Choose a compatible format (e.g. GGUF for llama.cpp, AWQ/GPTQ for vLLM, or unquantized 16-bit precision).",
            log_info=log_info,
            code=ApexErrorCode.MODEL_LOAD_FAILED,
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
            code=ApexErrorCode.CUDA_OUT_OF_MEMORY,
        )


class CacheCorruptedError(RuntimeErrorBase):
    """Raised when cached model files fail integrity verification."""

    def __init__(self, cache_path: str, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Model cache corruption detected at: '{cache_path}'",
            cause=f"Model files failed sha256 checksum or size verification. Details: {details}",
            recovery="Clear the cached files for this model and redownload.",
            log_info=log_info,
            code=ApexErrorCode.MODEL_FILES_INVALID,
        )


class InvalidConfigurationError(RuntimeErrorBase):
    """Raised when configuration values are incompatible."""

    def __init__(self, key: str, value: Any, reason: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Invalid configuration parameter: '{key}' = {value}",
            cause=f"Validation constraints failed: {reason}",
            recovery="Adjust config value according to the documentation schemas.",
            log_info=log_info,
            code=ApexErrorCode.GENERAL_RUNTIME_ERROR,
        )


class StreamingFailureError(RuntimeErrorBase):
    """Raised when streaming generation fails mid-stream."""

    def __init__(self, model_id: str, reason: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Streaming generation failure on model '{model_id}'",
            cause=f"The underlying engine adapter encountered an internal error during iteration: {reason}",
            recovery="Restart the inference engine runtime session or clear context.",
            log_info=log_info,
            code=ApexErrorCode.PUBLIC_INFERENCE_FAILED,
        )


class GPUNotAvailableError(RuntimeErrorBase):
    """Raised when GPU is required or expected but unavailable."""

    def __init__(self, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message="No CUDA GPU device detected in runtime.",
            cause=f"PyTorch could not find an available CUDA device: {details}",
            recovery="In Google Colab, change runtime type to GPU (Runtime > Change runtime type > T4 GPU).",
            log_info=log_info,
            code=ApexErrorCode.GPU_NOT_AVAILABLE,
        )


class DependencyInstallationError(RuntimeErrorBase):
    """Raised when automatic dependency installation fails."""

    def __init__(self, package_name: str, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Failed to install required dependency: '{package_name}'",
            cause=f"Subprocess pip install failed: {details}",
            recovery="Verify network connectivity and run `pip install <package>` manually in a terminal.",
            log_info=log_info,
            code=ApexErrorCode.DEPENDENCY_INSTALLATION_FAILED,
        )


class APIStartupError(RuntimeErrorBase):
    """Raised when API server fails to bind or initialize."""

    def __init__(self, reason: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"API server startup failed: {reason}",
            cause="Uvicorn failed to bind, port conflict, or unhandled worker error.",
            recovery="Verify port availability and check server logs.",
            log_info=log_info,
            code=ApexErrorCode.API_STARTUP_FAILED,
        )


class APIHealthCheckError(RuntimeErrorBase):
    """Raised when API server fails local health check."""

    def __init__(self, endpoint: str, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"API health check failed on '{endpoint}'.",
            cause=f"Server did not return HTTP 200 within timeout: {details}",
            recovery="Inspect server exception logs and verify route configuration.",
            log_info=log_info,
            code=ApexErrorCode.API_HEALTH_CHECK_FAILED,
        )


class CloudflaredNotFoundError(RuntimeErrorBase):
    """Raised when cloudflared binary is not found and cannot be installed."""

    def __init__(self, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message="cloudflared executable not found and auto-install failed.",
            cause=f"Binary missing or unsupported architecture: {details}",
            recovery="Install cloudflared manually or switch to 'local' transport.",
            log_info=log_info,
            code=ApexErrorCode.CLOUDFLARED_NOT_FOUND,
        )


class TunnelStartupError(RuntimeErrorBase):
    """Raised when tunnel fails to start or establish connection."""

    def __init__(self, reason: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Cloudflare tunnel startup failed: {reason}",
            cause="Tunnel subprocess crashed, timed out, or connection failed.",
            recovery="Check network connectivity or restart the runtime.",
            log_info=log_info,
            code=ApexErrorCode.TUNNEL_STARTUP_FAILED,
        )


class TunnelUrlNotFoundError(RuntimeErrorBase):
    """Raised when tunnel fails to produce a public URL."""

    def __init__(self, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message="Cloudflare tunnel public URL could not be obtained.",
            cause=f"Log output did not contain valid trycloudflare.com URL within timeout: {details}",
            recovery="Check if Cloudflare network is reachable.",
            log_info=log_info,
            code=ApexErrorCode.TUNNEL_URL_NOT_FOUND,
        )


class PublicEndpointUnavailableError(RuntimeErrorBase):
    """Raised when public URL is not reachable externally."""

    def __init__(self, url: str, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Public endpoint '{url}' is unavailable.",
            cause=f"External verification request failed: {details}",
            recovery="Check firewall or try restarting the tunnel.",
            log_info=log_info,
            code=ApexErrorCode.PUBLIC_ENDPOINT_UNAVAILABLE,
        )


class PublicInferenceFailedError(RuntimeErrorBase):
    """Raised when end-to-end public inference request fails."""

    def __init__(self, details: str = "", log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message="End-to-end public model inference failed.",
            cause=f"Inference request through public endpoint returned an error: {details}",
            recovery="Verify model readiness and check API request logs.",
            log_info=log_info,
            code=ApexErrorCode.PUBLIC_INFERENCE_FAILED,
        )


class ModelLoadFailedError(RuntimeErrorBase):
    """Raised when model loading or warmup inference fails."""

    def __init__(self, model_id: str, reason: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Failed to load model '{model_id}': {reason}",
            cause=f"Model loading or warmup inference failed: {reason}",
            recovery="Check GPU VRAM, verify model files, or use a smaller precision/model.",
            log_info=log_info,
            code=ApexErrorCode.MODEL_LOAD_FAILED,
        )


class ModelFilesInvalidError(RuntimeErrorBase):
    """Raised when model directory or weights are incomplete/invalid."""

    def __init__(self, model_id: str, reason: str, log_info: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Model files for '{model_id}' are invalid or incomplete: {reason}",
            cause=f"Missing config, missing weights, 0-byte files, or corrupt JSON: {reason}",
            recovery="Clear cache and redownload the model.",
            log_info=log_info,
            code=ApexErrorCode.MODEL_FILES_INVALID,
        )
