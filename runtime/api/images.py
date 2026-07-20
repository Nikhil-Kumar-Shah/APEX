"""Images API for APEX Runtime."""

from fastapi import APIRouter
from runtime.api.errors import openai_error_response

router = APIRouter()

@router.post("/v1/images/generations")
async def image_gen_stub():
    return openai_error_response(
        message="Image generation is not currently supported by this APEX runtime.",
        error_type="not_implemented_error",
        code="endpoint_not_implemented",
        status_code=501,
        details={"resolution": "A future release will integrate an image generation model."}
    )

@router.post("/v1/images/edits")
async def image_edit_stub():
    return openai_error_response(
        message="Image editing operations are not yet available.",
        error_type="not_implemented_error",
        code="endpoint_not_implemented",
        status_code=501,
        details={"resolution": "A future release will integrate image editing capabilities."}
    )

@router.post("/v1/images/variations")
async def image_var_stub():
    return openai_error_response(
        message="Image variation generation is not supported in the current APEX runtime version.",
        error_type="not_implemented_error",
        code="endpoint_not_implemented",
        status_code=501,
        details={"resolution": "A future release will integrate image variation capabilities."}
    )
