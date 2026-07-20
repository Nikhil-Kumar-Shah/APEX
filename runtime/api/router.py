"""Main API router for APEX Universal Runtime."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.requests import Request
from runtime.api import (
    models, chat, completion, embeddings, vision, images, 
    audio, files, responses, health, runtime, version, websocket
)

def create_router(state, queue, model_manager) -> APIRouter:
    """Creates the root API router assembling all sub-routers."""
    
    router = APIRouter()
    
    @router.get("/", tags=["Root"])
    async def landing_page(request: Request):
        """Developer landing page for APEX."""
        accept_header = request.headers.get("accept", "")
        
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
                "/v1/embeddings",
                "/health",
                "/runtime",
                "/version",
                "/ws"
            ],
            "message": "APEX Runtime is running and ready to accept OpenAI-compatible requests."
        }
        
        if "text/html" in accept_header:
            html_content = f"""
            <!DOCTYPE html>
            <html>
                <head>
                    <title>APEX Runtime</title>
                    <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #0d1117; color: #c9d1d9; padding: 40px; text-align: center; }}
                        h1 {{ color: #58a6ff; font-size: 3em; margin-bottom: 10px; }}
                        p {{ font-size: 1.2em; color: #8b949e; }}
                        .container {{ max-width: 800px; margin: 0 auto; background-color: #161b22; padding: 30px; border-radius: 8px; border: 1px solid #30363d; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
                        a {{ color: #58a6ff; text-decoration: none; }}
                        a:hover {{ text-decoration: underline; }}
                        .endpoints {{ text-align: left; background-color: #0d1117; padding: 20px; border-radius: 6px; border: 1px solid #30363d; font-family: monospace; color: #a5d6ff; margin-top: 20px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>APEX</h1>
                        <p>{data["description"]}</p>
                        <p><strong>Version:</strong> {data["version"]} | <strong>Status:</strong> {data["status"]}</p>
                        <p>{data["message"]}</p>
                        <div class="endpoints">
                            <h3>Supported API Endpoints</h3>
                            <ul>
                                {"".join(f"<li>{e}</li>" for e in data["supported_endpoints"])}
                            </ul>
                        </div>
                        <p style="margin-top: 30px;">
                            <a href="{data["docs"]}">API Documentation</a> | 
                            <a href="{data["repository"]}">GitHub Repository</a>
                        </p>
                    </div>
                </body>
            </html>
            """
            return HTMLResponse(content=html_content)
        
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
