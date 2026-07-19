"""FastAPI exception handlers mapping core runtime errors to OpenAI compliant JSON."""

import logging
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from runtime.core.errors import (
    AuthenticationFailedError,
    CacheCorruptedError,
    DownloadFailedError,
    EngineUnavailableError,
    GPUOutOfMemoryError,
    InvalidConfigurationError,
    ModelNotFoundError,
    RuntimeErrorBase,
)

logger = logging.getLogger("runtime.server.errors")


def make_openai_error_response(
    message: str,
    code: str,
    status_code: int = 500,
    param: Optional[str] = None,
    err_type: str = "internal_error",
) -> JSONResponse:
    """Helper to structure an OpenAI-compliant error dictionary payload.

    Args:
        message: Human readable error explanation.
        code: Machine readable error slug.
        status_code: HTTP response status code.
        param: Optional request parameter trigger.
        err_type: OpenAI error type category.

    Returns:
        JSONResponse: Configured FastAPI response.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": err_type,
                "param": param,
                "code": code,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Binds exception handlers mapping custom exceptions to HTTP status codes."""

    @app.exception_handler(ModelNotFoundError)
    async def model_not_found_handler(request: Request, exc: ModelNotFoundError):
        logger.error(f"ModelNotFound: {exc.message}")
        return make_openai_error_response(
            message=f"{exc.message}. {exc.recovery}",
            code="model_not_found",
            status_code=404,
            err_type="invalid_request_error",
        )

    @app.exception_handler(AuthenticationFailedError)
    async def auth_failed_handler(request: Request, exc: AuthenticationFailedError):
        logger.error(f"AuthFailed: {exc.message}")
        return make_openai_error_response(
            message=f"{exc.message}. {exc.recovery}",
            code="authentication_failed",
            status_code=401,
            err_type="invalid_request_error",
        )

    @app.exception_handler(GPUOutOfMemoryError)
    async def gpu_oom_handler(request: Request, exc: GPUOutOfMemoryError):
        logger.critical(f"GPU OOM: {exc.message}")
        return make_openai_error_response(
            message=f"{exc.message}. {exc.recovery}",
            code="gpu_out_of_memory",
            status_code=503,
            err_type="server_error",
        )

    @app.exception_handler(EngineUnavailableError)
    async def engine_unavailable_handler(request: Request, exc: EngineUnavailableError):
        logger.error(f"EngineUnavailable: {exc.message}")
        return make_openai_error_response(
            message=f"{exc.message}. {exc.recovery}",
            code="engine_unavailable",
            status_code=503,
            err_type="server_error",
        )

    @app.exception_handler(DownloadFailedError)
    async def download_failed_handler(request: Request, exc: DownloadFailedError):
        logger.error(f"DownloadFailed: {exc.message}")
        return make_openai_error_response(
            message=f"{exc.message}. {exc.recovery}",
            code="download_failed",
            status_code=502,
            err_type="server_error",
        )

    @app.exception_handler(InvalidConfigurationError)
    async def config_invalid_handler(request: Request, exc: InvalidConfigurationError):
        logger.error(f"InvalidConfiguration: {exc.message}")
        return make_openai_error_response(
            message=f"{exc.message}. {exc.recovery}",
            code="invalid_configuration",
            status_code=400,
            err_type="invalid_request_error",
        )

    @app.exception_handler(RuntimeErrorBase)
    async def runtime_base_handler(request: Request, exc: RuntimeErrorBase):
        logger.error(f"RuntimeErrorBase: {exc.message}")
        return make_openai_error_response(
            message=f"{exc.message}. {exc.recovery}",
            code="runtime_error",
            status_code=500,
            err_type="server_error",
        )
