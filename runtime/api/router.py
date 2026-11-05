"""Main API router for APEX Universal Runtime."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.requests import Request
from runtime.api import (
    models, chat, completion, embeddings, vision, images, 
    audio, files, responses, health, runtime, version, websocket
)
from runtime.api.web_interface import get_web_interface_html


def create_router(state, queue, model_manager) -> APIRouter:
    """Creates the root API router assembling all sub-routers."""
    
    router = APIRouter()
    
    @router.get("/", tags=["Root"])
    @router.get("/chat", tags=["Root"])
    async def landing_page(request: Request):
        """APEX AI Communication Interface & service landing endpoint."""
        accept_header = request.headers.get("accept", "")

        # If requested from browser or explicit /chat path, render the AI Communication Interface
        if request.url.path == "/chat" or "text/html" in accept_header:
            return HTMLResponse(content=get_web_interface_html())

        data = {
            "project": "APEX",
            "description": "Adaptive Platform for Unified AI Configuration, Orchestration and Workspace Management",
            "version": "1.2.0",
            "status": "online",
            "repository": "https://github.com/Nikhil-Kumar-Shah/APEX",
            "license": "MIT",
            "docs": "/docs",
            "supported_endpoints": [
                "/v1/models",
                "/v1/chat/completions",
                "/v1/completions",
                "/v1/files",
                "/v1/conversations",
                "/v1/embeddings",
                "/health",
                "/runtime",
                "/version",
                "/ws"
            ],
            "message": "APEX Runtime is running and ready to accept OpenAI-compatible requests."
        }
        return JSONResponse(content=data)

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
