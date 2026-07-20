"""Main API router for APEX Universal Runtime."""

from fastapi import APIRouter
from runtime.api import (
    models, chat, completion, embeddings, vision, images, 
    audio, files, responses, health, runtime, version, websocket
)

def create_router(state, queue, model_manager) -> APIRouter:
    """Creates the root API router assembling all sub-routers."""
    
    # We can inject state, queue, or model_manager into routers if needed via dependencies
    # For now, we just include them all
    
    router = APIRouter()
    
    router.include_router(models.router, tags=["Models"])
    router.include_router(chat.router, tags=["Chat"])
    router.include_router(completion.router, tags=["Completions"])
    router.include_router(embeddings.router, tags=["Embeddings"])
    router.include_router(vision.router, tags=["Vision"])
    router.include_router(images.router, tags=["Images"])
    router.include_router(audio.router, tags=["Audio"])
    router.include_router(files.router, tags=["Files"])
    router.include_router(responses.router, tags=["Responses"])
    router.include_router(health.router, tags=["Health"])
    router.include_router(runtime.router, tags=["Runtime"])
    router.include_router(version.router, tags=["Version"])
    router.include_router(websocket.router, tags=["WebSocket"])
    
    return router
