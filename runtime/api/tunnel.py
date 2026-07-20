"""Tunnel Provider Interface and Implementations."""

import subprocess
import time
import re
import logging
import threading
from typing import Optional

from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState

logger = logging.getLogger("runtime.api.tunnel")

class TunnelManager:
    """Manages secure remote access tunnels."""
    
    def __init__(self, config: APIConfig, state: RuntimeState):
        self.config = config
        self.state = state
        self.process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self):
        """Starts the configured tunnel provider."""
        if self.config.transport == "local":
            return

        if self.config.transport.lower() == "cloudflare":
            self._start_cloudflare()
        else:
            logger.warning(f"Unsupported transport: {self.config.transport}")

    def _start_cloudflare(self):
        """Starts a Cloudflare quick tunnel via cloudflared."""
        try:
            logger.info("Starting Cloudflare tunnel...", extra={"prefix": "SYSTEM"})
            # In a real environment, we'd check if cloudflared is installed.
            # Assuming it is installed by the bootstrap or environment.
            cmd = ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{self.state.port}"]
            
            # cloudflared writes logs to stderr
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            self._thread = threading.Thread(target=self._monitor_cloudflare, daemon=True)
            self._thread.start()
            
        except FileNotFoundError:
            logger.error("cloudflared executable not found. Cannot start tunnel.")
        except Exception as e:
            logger.error(f"Failed to start Cloudflare tunnel: {e}")

    def _monitor_cloudflare(self):
        """Monitors cloudflared stderr to extract the public URL."""
        if not self.process or not self.process.stderr:
            return
            
        url_regex = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        
        while not self._stop_event.is_set():
            line = self.process.stderr.readline()
            if not line:
                break
                
            match = url_regex.search(line)
            if match and not self.state.tunnel_connected:
                url = match.group(0)
                self.state.public_url = url
                self.state.tunnel_connected = True
                logger.info(f"Tunnel Online: {url}", extra={"prefix": "SUCCESS"})
                
        # If we exit the loop, the process died
        self.state.tunnel_connected = False
        self.state.public_url = None

    def stop(self):
        """Stops the tunnel."""
        self._stop_event.set()
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        
        self.state.tunnel_connected = False
        self.state.public_url = None
        logger.info("Tunnel stopped.", extra={"prefix": "SYSTEM"})
