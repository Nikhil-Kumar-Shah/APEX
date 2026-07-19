"""Public tunnel abstraction manager."""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("runtime.server.tunnel")


class TunnelManager:
    """Manages public URL endpoints to expose the local API server outside Google Colab."""

    def __init__(self, enabled: bool = False, provider: str = "ngrok", token: Optional[str] = None):
        """Initializes the TunnelManager.

        Args:
            enabled: If True, try to boot a tunnel on startup.
            provider: Tunnel provider name (defaults to 'ngrok').
            token: Optional authentication token required by provider.
        """
        self.enabled = enabled
        self.provider = provider
        self.token = token
        self.public_url: Optional[str] = None
        self._ngrok_process = None

    def start(self, port: int) -> Optional[str]:
        """Starts the public tunnel.

        Args:
            port: Local port to bind.

        Returns:
            Optional[str]: The public URL, or None if failed/disabled.
        """
        if not self.enabled:
            logger.info("Public tunnel is disabled in configuration.")
            return None

        logger.info(f"Starting public tunnel using provider '{self.provider}'...")

        if self.provider.lower() == "ngrok":
            try:
                from pyngrok import ngrok

                if self.token:
                    ngrok.set_auth_token(self.token)

                # Connect to ngrok tunnel
                self.public_url = ngrok.connect(port).public_url
                logger.info(f"[+] Public Tunnel Active: {self.public_url}")
                return self.public_url
            except ImportError:
                logger.warning("[-] 'pyngrok' is not installed. Public tunnel could not be initialized.")
                logger.warning("    Please install it using: pip install pyngrok")
            except Exception as e:
                logger.error(f"[-] Failed to start ngrok tunnel: {e}")
        else:
            logger.warning(f"[-] Unsupported tunnel provider: {self.provider}")

        return None

    def stop(self) -> None:
        """Stops the public tunnel and releases resources."""
        if not self.enabled or not self.public_url:
            return

        logger.info("Stopping public tunnel...")
        if self.provider.lower() == "ngrok":
            try:
                from pyngrok import ngrok
                ngrok.kill()
                logger.info("[-] ngrok tunnel closed.")
            except Exception as e:
                logger.warning(f"Error closing ngrok tunnel: {e}")

        self.public_url = None

    def get_status(self) -> Dict[str, Any]:
        """Gets status parameters for diagnostics.

        Returns:
            Dict[str, Any]: Active state and URL.
        """
        return {
            "tunnel_enabled": self.enabled,
            "tunnel_provider": self.provider,
            "public_url": self.public_url,
            "is_active": self.public_url is not None,
        }
