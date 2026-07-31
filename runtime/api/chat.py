"""Chat API for APEX Runtime."""

import json
import asyncio
from typing import List, Any
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from runtime.api.schemas import ChatCompletionRequest
from runtime.api.serializers import serialize_chat_completion, serialize_chat_completion_chunk

router = APIRouter()

def format_chat_prompt(messages: List[Any], tokenizer: Any = None) -> str:
    """Formats chat messages into an instruction prompt."""
    raw_msgs = []
    for m in messages:
        if isinstance(m, dict):
            raw_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        else:
            raw_msgs.append({"role": getattr(m, "role", "user"), "content": getattr(m, "content", "")})

    if tokenizer and hasattr(tokenizer, "apply_chat_template") and callable(tokenizer.apply_chat_template):
        try:
            return tokenizer.apply_chat_template(raw_msgs, tokenize=False, add_generation_prompt=True)
        except Exception:
            pass

    # Standard ChatML fallback prompt (Qwen, Llama-3, etc.)
    parts = []
    for msg in raw_msgs:
        role = msg["role"]
        content = msg["content"]
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    parts.append("<|im_start|>assistant")
    return "\n".join(parts) + "\n"

@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, req: Request):
    """OpenAI-compatible Chat Completions with real model token generation."""
    model_manager = getattr(req.app.state, "model_manager", None)
    active_engine = getattr(model_manager, "active_engine", None) if model_manager else None

    # Check if a model engine is loaded and active
    if active_engine and getattr(active_engine, "is_loaded", False):
        tokenizer = getattr(active_engine, "tokenizer", None)
        prompt = format_chat_prompt(request.messages, tokenizer)
        
        gen_params = {
            "max_new_tokens": getattr(request, "max_tokens", 512) or 512,
            "temperature": getattr(request, "temperature", 0.7) or 0.7,
            "top_p": getattr(request, "top_p", 0.9) or 0.9,
        }

        if request.stream:
            async def generate_real_stream():
                yield f"data: {json.dumps(serialize_chat_completion_chunk(request.model, role='assistant'))}\n\n"
                
                # Iterate over generated tokens from engine
                token_stream = active_engine.generate_stream(prompt, gen_params)
                for token in token_stream:
                    if token:
                        yield f"data: {json.dumps(serialize_chat_completion_chunk(request.model, content=token))}\n\n"
                        await asyncio.sleep(0)

                yield f"data: {json.dumps(serialize_chat_completion_chunk(request.model, finish_reason='stop'))}\n\n"
                yield f"data: [DONE]\n\n"

            return StreamingResponse(generate_real_stream(), media_type="text/event-stream")
        else:
            full_text = ""
            for token in active_engine.generate_stream(prompt, gen_params):
                full_text += token
            return serialize_chat_completion(
                model=request.model,
                content=full_text,
                prompt_tokens=len(prompt.split()),
                completion_tokens=len(full_text.split())
            )

    # Fallback response if no active model engine is present
    if request.stream:
        async def mock_stream():
            yield f"data: {json.dumps(serialize_chat_completion_chunk(request.model, role='assistant', content='Hello World! I am APEX.'))}\n\n"
            yield f"data: {json.dumps(serialize_chat_completion_chunk(request.model, finish_reason='stop'))}\n\n"
            yield f"data: [DONE]\n\n"
        return StreamingResponse(mock_stream(), media_type="text/event-stream")

    return serialize_chat_completion(
        model=request.model,
        content="Hello World! I am APEX.",
        prompt_tokens=10,
        completion_tokens=20
    )
