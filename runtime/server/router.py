"""FastAPI router implementing OpenAI-compatible endpoints and server diagnostics."""

import json
import logging
import uuid
from typing import AsyncGenerator, Generator, Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from runtime.server.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatCompletionStreamChoice,
    ChatCompletionStreamDelta,
    ChatCompletionStreamResponse,
    ChatCompletionUsage,
    ModelInfo,
    ModelListResponse,
)
from runtime.server.errors import make_openai_error_response
from runtime.server.queue import QueueFullError

logger = logging.getLogger("runtime.server.router")
router = APIRouter()


def format_messages_to_prompt(messages: list) -> str:
    """Helper to convert OpenAI message lists into standard ChatML prompt format.

    Args:
        messages: List of chat message objects.

    Returns:
        str: Converted text prompt.
    """
    prompt = ""
    for msg in messages:
        role = msg.role
        content = msg.content
        prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
    prompt += "<|im_start|>assistant\n"
    return prompt


@router.get("/health")
async def health():
    """Simple endpoint to verify server is reachable."""
    return {"status": "ok"}


@router.get("/status")
async def status(request: Request):
    """Provides a detailed system and server diagnostic report."""
    app = request.app
    health_monitor = app.state.health_monitor
    conn_manager = app.state.conn_manager
    queue_mgr = app.state.queue_manager

    report = health_monitor.generate_report()
    report["server"] = conn_manager.get_stats()
    report["queue"] = queue_mgr.get_status()
    return report


@router.get("/v1/models", response_model=ModelListResponse)
async def list_models(request: Request):
    """Lists cached models formatted in OpenAI compatible schema."""
    model_manager = request.app.state.model_manager
    cached = model_manager.list_cached_models()

    models = [ModelInfo(id=m["model_id"]) for m in cached]
    
    # If no models are cached yet, offer a fallback default ID
    if not models:
        models.append(ModelInfo(id=model_manager.active_model_id or "default-model"))
        
    return ModelListResponse(data=models)


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, payload: ChatCompletionRequest):
    """OpenAI compatible Chat Completions endpoint."""
    app = request.app
    model_manager = app.state.model_manager
    queue_mgr = app.state.queue_manager
    conn_manager = app.state.conn_manager

    # 1. Validate loaded model compatibility
    if not model_manager.active_model_id:
        return make_openai_error_response(
            message="No model is currently loaded. Load a model via ModelManager first.",
            code="model_unavailable",
            status_code=503,
            err_type="server_error",
        )

    # Track active connection client IP
    client_ip = request.client.host if request.client else "unknown"
    conn_manager.register_connection(client_ip)

    # 2. Formulate prompt
    prompt = format_messages_to_prompt(payload.messages)

    # Map generation options
    gen_params = {
        "temperature": payload.temperature,
        "top_p": payload.top_p,
        "max_new_tokens": payload.max_tokens or 512,
        "repetition_penalty": payload.repetition_penalty,
    }

    try:
        # Enqueue request to prevent concurrent GPU thrashing
        token_queue, cancel_event = await queue_mgr.enqueue_request(prompt, gen_params)
    except QueueFullError as e:
        conn_manager.deregister_connection(client_ip)
        return make_openai_error_response(
            message=str(e),
            code="queue_full",
            status_code=429,
            err_type="server_error",
        )

    # 3. Stream or Non-stream dispatch
    if payload.stream:
        async def event_generator() -> AsyncGenerator[str, None]:
            choice_id = f"chatcmpl-{uuid.uuid4()}"
            try:
                while True:
                    # Check if client disconnected mid-flight
                    if await request.is_disconnected():
                        cancel_event.set()
                        logger.info(f"Client {client_ip} disconnected. Cancelling stream.")
                        break

                    token = await token_queue.get()
                    if token is None:
                        break

                    chunk = ChatCompletionStreamResponse(
                        id=choice_id,
                        model=model_manager.active_model_id,
                        choices=[
                            ChatCompletionStreamChoice(
                                index=0,
                                delta=ChatCompletionStreamDelta(content=token),
                            )
                        ],
                    )
                    yield f"data: {json.dumps(chunk.dict())}\n\n"
                
                # Yield termination signal
                yield "data: [DONE]\n\n"
            finally:
                conn_manager.deregister_connection(client_ip)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    else:
        # Resolve non-streaming completion request
        choice_id = f"chatcmpl-{uuid.uuid4()}"
        generated_tokens = []
        try:
            while True:
                # Check for cancellation/disconnect
                if await request.is_disconnected():
                    cancel_event.set()
                    break

                token = await token_queue.get()
                if token is None:
                    break
                generated_tokens.append(token)

            full_content = "".join(generated_tokens)
            response = ChatCompletionResponse(
                id=choice_id,
                model=model_manager.active_model_id,
                choices=[
                    ChatCompletionResponseChoice(
                        index=0,
                        message=payload.messages[-1],  # mock or standard response representation
                    )
                ],
                usage=ChatCompletionUsage(
                    prompt_tokens=len(prompt) // 4,
                    completion_tokens=len(full_content) // 4,
                    total_tokens=(len(prompt) + len(full_content)) // 4,
                ),
            )
            # Update choices message to be the newly generated text
            response.choices[0].message.role = "assistant"
            response.choices[0].message.content = full_content
            return response
        finally:
            conn_manager.deregister_connection(client_ip)
