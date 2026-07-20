"""Completion API for APEX Runtime."""

from fastapi import APIRouter
from runtime.api.schemas import CompletionRequest

router = APIRouter()

@router.post("/v1/completions")
async def completions(request: CompletionRequest):
    """OpenAI-compatible classic completions."""
    return {
        "id": "cmpl-mock",
        "object": "text_completion",
        "created": 1234567890,
        "model": request.model,
        "choices": [
            {
                "text": " Mock completion output.",
                "index": 0,
                "logprobs": None,
                "finish_reason": "length"
            }
        ],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 5,
            "total_tokens": 10
        }
    }
