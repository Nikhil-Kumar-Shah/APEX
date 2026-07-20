"""Responses API for APEX Runtime."""

from fastapi import APIRouter
from runtime.api.errors import openai_error_response

router = APIRouter()

@router.post("/v1/responses")
async def unified_responses():
    """Future-proof unified endpoint."""
    return openai_error_response(
        message="The unified responses endpoint is a placeholder for future generic requests and is not currently functional.",
        error_type="not_implemented_error",
        code="endpoint_not_implemented",
        status_code=501,
        details={"resolution": "Please use specific endpoints like /v1/chat/completions or /v1/embeddings instead."}
    )
