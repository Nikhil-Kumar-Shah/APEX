"""Completion API for APEX Runtime with real engine inference."""

import time
from fastapi import APIRouter, Request, HTTPException
from runtime.api.schemas import CompletionRequest

router = APIRouter()


@router.post("/v1/completions")
async def completions(request: CompletionRequest, req: Request):
    """OpenAI-compatible classic text completions."""
    model_manager = getattr(req.app.state, "model_manager", None)
    active_engine = getattr(model_manager, "active_engine", None) if model_manager else None

    if not active_engine or not getattr(active_engine, "is_loaded", False):
        raise HTTPException(
            status_code=503,
            detail="No model is currently loaded in APEX runtime. Load a model first before sending requests.",
        )

    prompt = request.prompt
    if isinstance(prompt, list):
        prompt = " ".join(str(p) for p in prompt)

    gen_params = {
        "max_new_tokens": request.max_tokens or 64,
        "temperature": request.temperature or 0.7,
        "top_p": request.top_p or 0.9,
    }

    generated_text = ""
    for token in active_engine.generate_stream(prompt, gen_params):
        generated_text += token

    prompt_tokens = len(str(prompt).split())
    completion_tokens = len(generated_text.split())

    return {
        "id": f"cmpl-{int(time.time()*1000)}",
        "object": "text_completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [
            {
                "text": generated_text,
                "index": 0,
                "logprobs": None,
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
