"""FastAPI Application setup and server lifecycle management."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from runtime.core.health import HealthMonitor
from runtime.model.manager import ModelManager
from runtime.server.connection import ConnectionManager
from runtime.server.errors import register_exception_handlers
from runtime.server.queue import RequestQueue
from runtime.server.router import router
from runtime.server.session import SessionManager
from runtime.server.tunnel import TunnelManager

logger = logging.getLogger("runtime.server.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Orchestrates API Server startup and shutdown hooks."""
    # 1. Startup: Launch queue worker and open public tunnel if configured
    app.state.queue_manager.start_worker(app.state.model_manager)
    
    # Expose tunnel asynchronously
    port = app.state.server_port
    if app.state.tunnel_manager.enabled:
        # Run in separate thread to prevent blocking Uvicorn startup
        await asyncio.to_thread(app.state.tunnel_manager.start, port)

    yield

    # 2. Shutdown: Clean up background processes and close tunnels
    await app.state.queue_manager.stop_worker()
    if app.state.tunnel_manager.enabled:
        await asyncio.to_thread(app.state.tunnel_manager.stop)


def create_app(
    model_manager: ModelManager,
    health_monitor: HealthMonitor,
    server_port: int = 8000,
    queue_max_size: int = 10,
    session_timeout: float = 600.0,
    tunnel_enabled: bool = False,
    tunnel_token: Optional[str] = None,
) -> FastAPI:
    """Configures and builds the FastAPI application instance.

    Args:
        model_manager: The active ModelManager instance.
        health_monitor: The active HealthMonitor instance.
        server_port: The port the server is binding to.
        queue_max_size: Max requests buffered.
        session_timeout: Session expiration time in seconds.
        tunnel_enabled: Whether to start ngrok tunnel.
        tunnel_token: Ngrok authentication token.

    Returns:
        FastAPI: The configured application instance.
    """
    app = FastAPI(
        title="APEX Runtime API",
        version="1.0.0",
        lifespan=lifespan,
    )


    # Enable CORS for external client applications (e.g. Continue/Cline extensions)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Bind internal Managers and states
    app.state.model_manager = model_manager
    app.state.health_monitor = health_monitor
    app.state.server_port = server_port
    app.state.conn_manager = ConnectionManager()
    app.state.session_manager = SessionManager(session_timeout)
    app.state.queue_manager = RequestQueue(max_size=queue_max_size)
    app.state.tunnel_manager = TunnelManager(enabled=tunnel_enabled, token=tunnel_token)

    # Register routers and exception handlers
    app.include_router(router)
    register_exception_handlers(app)

    return app


def run_server(app: FastAPI, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Starts the Uvicorn web server synchronous loop.

    Args:
        app: The FastAPI application instance.
        host: Interface host address.
        port: Bind port.
    """
    logger.info(f"Starting API Server on {host}:{port}...")
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    server.run()
