"""Security formatters and exception handlers."""

import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("runtime.api.security")

async def secure_exception_handler(request: Request, exc: Exception):
    """Formats all unhandled exceptions into secure 500 JSON Responses without leaking tracebacks."""
    # We log the traceback internally to the backend console
    logger.error(f"Unhandled exception during API request: {str(exc)}", exc_info=True)
    
    # We return a generic error to the client
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "An internal server error occurred.",
                "type": "server_error",
                "param": None,
                "code": "500"
            }
        }
    )

def make_openai_error_response(message: str, type: str = "invalid_request_error", code: str = "400") -> JSONResponse:
    """Standardized OpenAI compatible error response."""
    status_code = int(code) if code.isdigit() else 400
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": type,
                "param": None,
                "code": code
            }
        }
    )
