"""Vision API for APEX Runtime."""

from fastapi import APIRouter
from runtime.api.errors import openai_error_response

router = APIRouter()

@router.post("/v1/vision")
async def vision_stub():
    return openai_error_response(
        message="The vision processing endpoint is not yet implemented in the current APEX runtime.",
        error_type="not_implemented_error",
        code="endpoint_not_implemented",
        status_code=501,
        details={"resolution": "Please wait for a future update that includes multimodal vision support."}
    )

@router.post("/v1/images/analyze")
async def analyze_stub():
    return openai_error_response(
        message="Image analysis capabilities are currently unavailable. The endpoint exists for future compatibility.",
        error_type="not_implemented_error",
        code="endpoint_not_implemented",
        status_code=501,
        details={"resolution": "Please wait for a future update that includes image analysis features."}
    )
