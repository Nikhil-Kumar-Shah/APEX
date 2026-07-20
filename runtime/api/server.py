"""FastAPI Application Factory."""

from fastapi import FastAPI, Depends, Request
from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState
from runtime.api.authentication import AuthManager
from runtime.api.queue import RequestQueue
from runtime.api.middleware import configure_cors, request_logging_middleware
from runtime.api.router import create_router
from runtime.api.security import secure_exception_handler

def create_app(
    config: APIConfig, 
    state: RuntimeState, 
    auth_manager: AuthManager, 
    queue: RequestQueue,
    model_manager
) -> FastAPI:
    """Builds and configures the FastAPI application."""
    app = FastAPI(title="APEX API", version="1.1", docs_url="/docs", redoc_url=None)

    # 1. Error Handlers
    app.add_exception_handler(Exception, secure_exception_handler)

    # 2. Middleware
    configure_cors(app, config)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        if config.enable_request_logs:
            from runtime.api.middleware import request_logging_middleware
            return await request_logging_middleware(request, call_next, state)
        return await call_next(request)

    # 3. Mount Routes (with Auth Dependency)
    async def auth_dependency(request: Request):
        return await auth_manager.verify_request(request)

    router = create_router(state, queue, model_manager)

    
    # We apply the auth dependency to all routes except root/health if we want,
    # but the prompt implies standard global auth. We can mount it on the router.
    app.include_router(
        router, 
        dependencies=[Depends(auth_dependency)] if config.enable_auth else []
    )

    return app
