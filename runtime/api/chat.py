"""Chat API for APEX Runtime."""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from runtime.api.schemas import ChatCompletionRequest
from runtime.api.serializers import serialize_chat_completion
import json

router = APIRouter()

@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, req: Request):
    """OpenAI-compatible Chat Completions."""
    if request.stream:
        async def mock_stream():
            yield f"data: {json.dumps(serialize_chat_completion(request.model, 'Hello! '))} \n\n"
            yield f"data: [DONE]\n\n"
        return StreamingResponse(mock_stream(), media_type="text/event-stream")
    
    return serialize_chat_completion(
        model=request.model,
        content="This is a mock chat completion response from the APEX runtime.",
        prompt_tokens=10,
        completion_tokens=20
    )
