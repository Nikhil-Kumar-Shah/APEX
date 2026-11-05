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
from typing import List, Optional

from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState

logger = logging.getLogger("runtime.api.tunnel")


class TunnelManager:
    """Manages secure remote access tunnels via Cloudflare Quick Tunnels."""

    def __init__(self, config: APIConfig, state: RuntimeState):
        self.config = config
        self.state = state
        self.process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._url_event = threading.Event()
        self.recent_logs: List[str] = []

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

        # 2. Setup repository-relative bin directory (stable regardless of working directory)
        repo_root = Path(__file__).resolve().parents[2]
        bin_dir = repo_root / "bin"
        bin_dir.mkdir(exist_ok=True)

        system = platform.system().lower()
        machine = platform.machine().lower()

        if system == "windows":
            binary_name = "cloudflared.exe"
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        elif system == "linux":
            binary_name = "cloudflared"
            if "arm" in machine or "aarch64" in machine:
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
            else:
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        elif system == "darwin":
            binary_name = "cloudflared"
            if "arm" in machine or "aarch64" in machine:
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64"
            else:
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64"
        else:
            logger.error(f"Unsupported OS for auto-install: {system}")
            return None

        binary_path = bin_dir / binary_name

        # If already downloaded in bin
        if binary_path.exists() and binary_path.stat().st_size > 0:
            return str(binary_path)

        # 3. Download
        logger.info(f"Downloading cloudflared for {system} ({machine})...", extra={"prefix": "SYSTEM"})
        try:
            urllib.request.urlretrieve(url, str(binary_path))
            if system != "windows":
                # Make executable
                st = os.stat(binary_path)
                os.chmod(binary_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            logger.info("cloudflared download complete.", extra={"prefix": "SUCCESS"})
            return str(binary_path)
        except Exception as e:
            logger.error(f"Failed to download cloudflared: {e}")
            if binary_path.exists():
                try:
                    binary_path.unlink()
                except OSError:
                    pass
            return None

    def _start_cloudflare(self) -> bool:
        """Starts a Cloudflare quick tunnel via cloudflared with non-blocking merged I/O."""
        binary_path = self._ensure_cloudflared_installed()
        if not binary_path:
            err = "cloudflared executable not found and could not be installed."
            self.state.last_error = err
            logger.error(err)
            return False

        try:
            logger.info("Starting Cloudflare tunnel...", extra={"prefix": "SYSTEM"})
            cmd = [binary_path, "tunnel", "--url", f"http://127.0.0.1:{self.state.port}"]

            self._stop_event.clear()
            self._url_event.clear()
            self.recent_logs = []

            # Merge stdout and stderr to prevent pipe buffer deadlocks and capture all output
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Give process a moment to verify it didn't immediately crash
            time.sleep(0.3)
            if self.process.poll() is not None:
                out = self.process.stdout.read() if self.process.stdout else ""
                err = f"cloudflared exited immediately (code {self.process.poll()}): {out.strip()}"
                self.state.last_error = err
                logger.error(err)
                return False

            self._thread = threading.Thread(target=self._monitor_cloudflare, daemon=True)
            self._thread.start()
            return True

        except Exception as e:
            err = f"Failed to start Cloudflare tunnel: {e}"
            self.state.last_error = err
            logger.error(err)
            return False

    def _monitor_cloudflare(self):
        """Monitors cloudflared unified stdout/stderr stream to extract the public URL."""
        if not self.process or not self.process.stdout:
            return

        url_regex = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

        while not self._stop_event.is_set():
            line = self.process.stdout.readline()
            if not line:
                if self.process and self.process.poll() is not None:
                    break
                time.sleep(0.1)
                continue

            clean_line = line.strip()
            if clean_line:
                self.recent_logs.append(clean_line)
                if len(self.recent_logs) > 50:
                    self.recent_logs.pop(0)

            match = url_regex.search(line)
            if match and not self.state.tunnel_connected:
                url = match.group(0)
                self.state.public_url = url
                self.state.tunnel_connected = True
                self._url_event.set()
                logger.info(f"Tunnel Online: {url}", extra={"prefix": "SUCCESS"})

        # If process exited abnormally while not requested to stop
        if not self._stop_event.is_set() and self.process and self.process.poll() is not None and self.process.poll() != 0:
            exit_code = self.process.poll()
            recent_err = " | ".join(self.recent_logs[-3:]) if self.recent_logs else "No logs"
            self.state.last_error = f"cloudflared process terminated with code {exit_code}: {recent_err}"
            logger.error(self.state.last_error)
            self.state.tunnel_connected = False
            self.state.public_url = None

    def wait_for_url(self, timeout_s: float = 25.0) -> Optional[str]:
        """Blocks until the public URL is obtained or timeout expires."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.state.public_url:
                return self.state.public_url
            if self.process and self.process.poll() is not None:
                return None
            if self._url_event.wait(timeout=0.25):
                return self.state.public_url
        return None

    def stop(self):
        """Stops the tunnel process cleanly."""
        self._stop_event.set()
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

        self.state.tunnel_connected = False
        self.state.public_url = None
        logger.info("Tunnel stopped.", extra={"prefix": "SYSTEM"})
