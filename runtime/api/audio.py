"""Audio API for APEX Runtime."""

from fastapi import APIRouter
from runtime.api.errors import openai_error_response

router = APIRouter()

@router.post("/v1/audio/transcriptions")
async def audio_transcription_stub():
    return openai_error_response(
        message="The audio transcription endpoint is currently under development. This feature is planned for a future release of the APEX runtime.",
        error_type="not_implemented_error",
        code="endpoint_not_implemented",
        status_code=501,
        details={"resolution": "Please check the documentation or upgrade your APEX runtime version when this feature becomes available."}
    )

@router.post("/v1/audio/translations")
async def audio_translation_stub():
    return openai_error_response(
        message="The audio translation endpoint is not yet supported by this APEX runtime version.",
        error_type="not_implemented_error",
        code="endpoint_not_implemented",
        status_code=501,
        details={"resolution": "Please check the documentation or upgrade your APEX runtime version when this feature becomes available."}
    )

@router.post("/v1/audio/speech")
async def audio_speech_stub():
    return openai_error_response(
        message="Text-to-speech generation is not currently implemented in this version of the APEX runtime.",
        error_type="not_implemented_error",
        code="endpoint_not_implemented",
        status_code=501,
        details={"resolution": "Please check the documentation or upgrade your APEX runtime version when this feature becomes available."}
    )
