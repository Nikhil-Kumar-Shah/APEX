"""FastAPI middleware configurations."""

import time
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState

logger = logging.getLogger("runtime.api.requests")

def configure_cors(app: FastAPI, config: APIConfig):
    """Configures CORS based on the selected mode."""
    if config.cors_mode.lower() == "developer":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    elif config.cors_mode.lower() == "restricted":
        # In a real environment, read origins from config
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )
    # If disabled, do not add the middleware

async def request_logging_middleware(request: Request, call_next, state: RuntimeState):
    """Logs incoming requests and execution time. Updates state counters."""
    start_time = time.time()
    
    # Pre-request
    state.total_requests += 1
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Log successful completion
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s",
            extra={"prefix": "API"}
        )
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"{request.method} {request.url.path} - ERROR - {duration:.3f}s",
            extra={"prefix": "API"}
        )
        raise
