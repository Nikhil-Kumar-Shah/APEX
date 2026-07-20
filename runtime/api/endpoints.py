"""OpenAI-Compatible Endpoints."""

import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from runtime.api.schemas import ChatCompletionRequest, CompletionRequest, ModelList, ModelInfo
from runtime.api.state import RuntimeState
from runtime.api.security import make_openai_error_response
from runtime.api.queue import RequestQueue

logger = logging.getLogger("runtime.api.endpoints")

def create_router(state: RuntimeState, queue: RequestQueue, model_manager) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def root():
        """Root status endpoint."""
        return {"status": "APEX API Online", "version": "1.1"}

    @router.get("/health")
    async def health():
        """Returns comprehensive JSON health state."""
        return {
            "api_running": state.api_running,
            "authentication_enabled": state.authentication == "Enabled",
            "tunnel_connected": state.tunnel_connected,
            "queue_size": state.queue_size,
            "model_loaded": state.model_loaded,
            "worker_alive": state.worker_alive,
            "workspace": state.workspace,
            "gpu": state.gpu_stats
        }

    @router.get("/v1/models", response_model=ModelList)
    async def list_models():
        """OpenAI-compatible models list endpoint."""
        models = []
        if state.model_loaded:
            models.append(ModelInfo(id=state.model_loaded))
        return ModelList(data=models)

    @router.post("/v1/chat/completions")
    async def chat_completions(request: ChatCompletionRequest):
        """OpenAI-compatible Chat Completions endpoint."""
        if not state.model_loaded:
            return make_openai_error_response("No model is currently loaded.", code="400")

        # Define the actual inference call
        async def _run_inference():
            # Standardize messages for the engine
            messages = [{"role": m.role, "content": m.content} for m in request.messages]
            
            try:
                # Simulate generation for now since we just swapped the backend layout
                # In full integration, this calls model_manager.generate() or similar
                if request.stream:
                    async def stream_generator():
                        yield 'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello "}}]}\n\n'
                        yield 'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"delta":{"content":"World!"}}]}\n\n'
                        yield 'data: [DONE]\n\n'
                    return StreamingResponse(stream_generator(), media_type="text/event-stream")
                else:
                    return {
                        "id": "chatcmpl-123",
                        "object": "chat.completion",
                        "created": 1686935002,
                        "model": request.model,
                        "choices": [{
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "Hello World! I am APEX."
                            },
                            "finish_reason": "stop"
                        }],
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                    }
            except Exception as e:
                logger.error(f"Inference error: {e}")
                raise

        # Execute safely via Queue
        return await queue.execute(_run_inference)

    @router.post("/v1/completions")
    async def completions(request: CompletionRequest):
        """OpenAI-compatible Completions endpoint (Legacy)."""
        if not state.model_loaded:
            return make_openai_error_response("No model is currently loaded.", code="400")

        async def _run_inference():
            try:
                if request.stream:
                    async def stream_generator():
                        yield 'data: {"id":"cmpl-123","object":"text_completion","choices":[{"text":" Hello","index":0}]}\n\n'
                        yield 'data: [DONE]\n\n'
                    return StreamingResponse(stream_generator(), media_type="text/event-stream")
                else:
                    return {
                        "id": "cmpl-123",
                        "object": "text_completion",
                        "created": 1686935002,
                        "model": request.model,
                        "choices": [{
                            "text": " Hello",
                            "index": 0,
                            "logprobs": None,
                            "finish_reason": "stop"
                        }],
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                    }
            except Exception as e:
                logger.error(f"Inference error: {e}")
                raise

        return await queue.execute(_run_inference)

    return router
