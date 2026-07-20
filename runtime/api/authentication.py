"""Authentication and Secret Management."""

import os
import secrets
import logging
from typing import Optional
from fastapi import Request, HTTPException, status

from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState

logger = logging.getLogger("runtime.api.auth")

class AuthManager:
    """Manages API key resolution and bearer token validation."""
    
    def __init__(self, config: APIConfig, state: RuntimeState):
        self.config = config
        self.state = state
        self._resolve_api_key()

    def _resolve_api_key(self):
        """Resolves the API key based on the strict hierarchy."""
        if not self.config.enable_auth:
            self.state.authentication = "Disabled"
            self.state.api_key = None
            return

        self.state.authentication = "Enabled"

        # 1. Environment Variable
        env_key = os.environ.get("APEX_API_KEY")
        if env_key:
            self.config.api_key = env_key
            self.state.api_key = env_key
            return

        # 2. Configuration (User passed via notebook/workspace)
        if self.config.api_key:
            self.state.api_key = self.config.api_key
            return

        # 3. Auto Generate
        if self.config.auto_generate_key:
            new_key = "APEX_" + secrets.token_urlsafe(32)
            self.config.api_key = new_key
            self.state.api_key = new_key
            return
            
        # Auth is enabled but no key exists and generation is disabled. 
        # This will block all requests, but is secure.
        logger.warning("Authentication is enabled but no API key is configured or generated.")
        self.state.api_key = None

    async def verify_request(self, request: Request):
        """Validates the Authorization Bearer token."""
        if not self.config.enable_auth:
            return True

        if not self.config.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication is required but no API key is configured on the server."
            )

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization header."
            )

        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format. Expected 'Bearer <token>'."
            )

        token = auth_header.split(" ")[1]
        
        # Use secrets.compare_digest to prevent timing attacks
        if not secrets.compare_digest(token, self.config.api_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key."
            )
            
        return True
