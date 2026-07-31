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
                    <title>APEX Runtime — Live Interface</title>
                    <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #0d1117; color: #c9d1d9; padding: 30px; margin: 0; }}
                        h1 {{ color: #58a6ff; font-size: 2.5em; margin-bottom: 5px; text-align: center; }}
                        p.subtitle {{ font-size: 1.1em; color: #8b949e; text-align: center; margin-bottom: 25px; }}
                        .container {{ max-width: 850px; margin: 0 auto; background-color: #161b22; padding: 25px; border-radius: 10px; border: 1px solid #30363d; box-shadow: 0 8px 16px rgba(0,0,0,0.4); }}
                        .status-badge {{ display: inline-block; background-color: #238636; color: #ffffff; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 0.9em; }}
                        .chat-box {{ background-color: #0d1117; padding: 20px; border-radius: 8px; border: 1px solid #30363d; margin-top: 20px; text-align: left; }}
                        .chat-box h3 {{ color: #58a6ff; margin-top: 0; display: flex; align-items: center; justify-content: space-between; }}
                        textarea {{ width: 100%; box-sizing: border-box; background-color: #161b22; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 12px; font-size: 1em; resize: vertical; min-height: 80px; font-family: inherit; }}
                        textarea:focus {{ outline: none; border-color: #58a6ff; }}
                        button {{ background-color: #238636; color: #ffffff; border: none; padding: 10px 20px; border-radius: 6px; font-size: 1em; cursor: pointer; font-weight: bold; margin-top: 10px; transition: background-color 0.2s; }}
                        button:hover {{ background-color: #2ea043; }}
                        button:disabled {{ background-color: #343942; color: #8b949e; cursor: not-allowed; }}
                        .response-area {{ background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px; margin-top: 15px; min-height: 60px; font-family: monospace; white-space: pre-wrap; word-break: break-word; color: #7ee787; display: none; }}
                        .endpoints {{ text-align: left; background-color: #0d1117; padding: 15px 20px; border-radius: 6px; border: 1px solid #30363d; font-family: monospace; color: #a5d6ff; margin-top: 20px; font-size: 0.9em; }}
                        a {{ color: #58a6ff; text-decoration: none; }}
                        a:hover {{ text-decoration: underline; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>APEX Runtime</h1>
                        <p class="subtitle">{data["description"]}</p>
                        <div style="text-align: center; margin-bottom: 15px;">
                            <span class="status-badge">● ONLINE</span>
                            <span style="margin-left: 15px; color: #8b949e;">Version {data["version"]}</span>
                        </div>

                        <!-- Live Playground Chat -->
                        <div class="chat-box">
                            <h3>⚡ Direct Model Playground <span>Instant Live Test</span></h3>
                            <textarea id="promptInput" placeholder="Type a prompt to test your model directly..."></textarea>
                            <div style="text-align: right;">
                                <button id="sendBtn" onclick="sendPrompt()">Send Request ➔</button>
                            </div>
                            <div id="responseArea" class="response-area"></div>
                        </div>

                        <div class="endpoints">
                            <h4 style="margin-top: 0; color: #8b949e;">Supported OpenAPI Endpoints</h4>
                            <ul style="margin: 0; padding-left: 20px;">
                                {"".join(f"<li>{e}</li>" for e in data["supported_endpoints"])}
                            </ul>
                        </div>

                        <p style="margin-top: 20px; text-align: center; font-size: 0.9em;">
                            <a href="{data["docs"]}">API Documentation</a> | 
                            <a href="{data["repository"]}">GitHub Repository</a>
                        </p>
                    </div>

                    <script>
                    async function sendPrompt() {{
                        const promptInput = document.getElementById("promptInput");
                        const responseArea = document.getElementById("responseArea");
                        const sendBtn = document.getElementById("sendBtn");
                        const userText = promptInput.value.trim();
                        if (!userText) return;

                        sendBtn.disabled = true;
                        responseArea.style.display = "block";
                        responseArea.textContent = "Connecting to APEX model engine...";

                        try {{
                            const res = await fetch("/v1/chat/completions", {{
                                method: "POST",
                                headers: {{ "Content-Type": "application/json" }},
                                body: JSON.stringify({{
                                    model: "default",
                                    messages: [{{ role: "user", content: userText }}],
                                    stream: true
                                }})
                            }});

                            if (!res.ok) {{
                                const err = await res.json().catch(() => ({{}}));
                                responseArea.textContent = "Error " + res.status + ": " + (err.detail || "Failed to generate response.");
                                sendBtn.disabled = false;
                                return;
                            }}

                            responseArea.textContent = "";
                            const reader = res.body.getReader();
                            const decoder = new TextDecoder("utf-8");
                            let buffer = "";

                            while (true) {{
                                const {{ done, value }} = await reader.read();
                                if (done) break;
                                buffer += decoder.decode(value, {{ stream: true }});
                                const lines = buffer.split("\\n");
                                buffer = lines.pop();

                                for (const line of lines) {{
                                    if (line.startsWith("data: ")) {{
                                        const dataStr = line.slice(6).trim();
                                        if (dataStr === "[DONE]") break;
                                        try {{
                                            const parsed = JSON.parse(dataStr);
                                            const content = parsed.choices?.[0]?.delta?.content || "";
                                            responseArea.textContent += content;
                                        }} catch(e) {{}}
                                    }}
                                }}
                            }}
                        }} catch (err) {{
                            responseArea.textContent = "Connection Error: " + err.message;
                        }} finally {{
                            sendBtn.disabled = false;
                        }}
                    }}
                    </script>
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
