"""Tunnel Provider Interface and Implementations."""

import subprocess
import time
import re
import logging
import threading
import os
import stat
import urllib.request
import platform
import shutil
from pathlib import Path
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

    def start(self) -> bool:
        """Starts the configured tunnel provider."""
        if self.config.transport == "local":
            return True

        if self.config.transport.lower() == "cloudflare":
            return self._start_cloudflare()
        else:
            logger.warning(f"Unsupported transport: {self.config.transport}")
            return False

    def _ensure_cloudflared_installed(self) -> Optional[str]:
        """Ensures cloudflared is installed, downloading it if necessary."""
        # 1. Check system PATH
        existing = shutil.which("cloudflared")
        if existing:
            return existing
            
        # 2. Setup local bin directory
        bin_dir = Path.cwd() / "bin"
        bin_dir.mkdir(exist_ok=True)
        
        system = platform.system().lower()
        if system == "windows":
            binary_name = "cloudflared.exe"
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        elif system == "linux":
            binary_name = "cloudflared"
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        elif system == "darwin":
            logger.error("Auto-install on macOS requires manual cloudflared installation (e.g. `brew install cloudflared`).")
            return None
        else:
            logger.error(f"Unsupported OS for auto-install: {system}")
            return None
            
        binary_path = bin_dir / binary_name
        
        # If already downloaded in bin
        if binary_path.exists():
            return str(binary_path)
            
        # 3. Download
        logger.info(f"Downloading cloudflared for {system}...", extra={"prefix": "SYSTEM"})
        try:
            urllib.request.urlretrieve(url, str(binary_path))
            if system != "windows":
                # Make executable
                st = os.stat(binary_path)
                os.chmod(binary_path, st.st_mode | stat.S_IEXEC)
            return str(binary_path)
        except Exception as e:
            logger.error(f"Failed to download cloudflared: {e}")
            if binary_path.exists():
                binary_path.unlink()
            return None

    def _start_cloudflare(self) -> bool:
        """Starts a Cloudflare quick tunnel via cloudflared."""
        binary_path = self._ensure_cloudflared_installed()
        if not binary_path:
            logger.error("cloudflared executable not found and could not be installed.")
            return False

        try:
            logger.info("Starting Cloudflare tunnel...", extra={"prefix": "SYSTEM"})
            cmd = [binary_path, "tunnel", "--url", f"http://127.0.0.1:{self.state.port}"]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            self._thread = threading.Thread(target=self._monitor_cloudflare, daemon=True)
            self._thread.start()
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Cloudflare tunnel: {e}")
            return False

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
