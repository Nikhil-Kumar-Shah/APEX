"""API Lifecycle Manager."""

import uvicorn
import logging
import threading
from typing import Optional

from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState
from runtime.api.authentication import AuthManager
from runtime.api.queue import RequestQueue
from runtime.api.tunnel import TunnelManager
from runtime.api.server import create_app

logger = logging.getLogger("runtime.api.manager")

class APIManager:
    """Manages the full lifecycle of the API Server, Auth, Tunnel, and Queue."""
    
    def __init__(self, config: APIConfig, state: RuntimeState, model_manager):
        self.config = config
        self.state = state
        self.model_manager = model_manager
        
        self.auth_manager = AuthManager(self.config, self.state)
        self.queue = RequestQueue(self.config, self.state)
        self.tunnel = TunnelManager(self.config, self.state)
        
        self.app = create_app(
            config=self.config,
            state=self.state,
            auth_manager=self.auth_manager,
            queue=self.queue,
            model_manager=self.model_manager
        )
        
        self._server_thread: Optional[threading.Thread] = None
        self._uvicorn_server: Optional[uvicorn.Server] = None

    def start(self):
        """Starts the API Server and Tunnels."""
        if not self.config.api_enabled:
            return

        self.tunnel.start()

        # Print banner
        print("====================================")
        print("APEX API")
        print("====================================")
        print(f"Running\nHost\n{self.config.host}\nPort\n{self.config.port}")
        
        auth_status = "Enabled" if self.config.enable_auth else "Disabled"
        print(f"Authentication\n{auth_status}")
        
        if self.config.enable_tunnel:
            print(f"Tunnel\n{self.config.tunnel_provider.capitalize()}")
            # Wait briefly for tunnel to grab URL
            import time
            time.sleep(2)
            url = self.state.public_url or "Waiting for URL..."
            print(f"Public URL\n{url}")
            print(f"OpenAI Endpoint\n{url}/v1")
        else:
            print("Tunnel\nDisabled")
            print(f"OpenAI Endpoint\nhttp://127.0.0.1:{self.config.port}/v1")
            
        print("====================================")

        uvicorn_config = uvicorn.Config(
            app=self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="error", # Suppress uvicorn spam, we log manually
            access_log=False
        )
        self._uvicorn_server = uvicorn.Server(uvicorn_config)
        
        self._server_thread = threading.Thread(target=self._uvicorn_server.run, daemon=True)
        self._server_thread.start()
        
        self.state.api_running = True

    def stop(self):
        """Stops the API and Tunnel."""
        self.tunnel.stop()
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True
            
        if self._server_thread:
            self._server_thread.join(timeout=3)
            
        self.state.api_running = False
        logger.info("API Manager stopped.", extra={"prefix": "SYSTEM"})
