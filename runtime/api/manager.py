"""API Lifecycle Manager with verified startup and Colab-aware networking."""

import sys
import time
import socket
import logging
import threading
import urllib.request
import urllib.error
from typing import Optional

import uvicorn

from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState, APIStatus
from runtime.api.authentication import AuthManager
from runtime.api.queue import RequestQueue
from runtime.api.tunnel import TunnelManager
from runtime.api.server import create_app

logger = logging.getLogger("runtime.api.manager")

# How long to poll for the server socket before declaring FAILED
_SOCKET_TIMEOUT_S = 15
_HEALTH_TIMEOUT_S = 10
_TUNNEL_TIMEOUT_S = 20
_POLL_INTERVAL_S = 0.3


class APIManager:
    """
    Manages the full lifecycle of the API Server, Auth, Tunnel, and Queue.

    Startup sequence (mirrors Docker):
        STOPPED → STARTING → socket bound → VERIFYING → /health 200 → RUNNING
        Any failure at any step → FAILED with last_error set.
    """

    def __init__(self, config: APIConfig, state: RuntimeState, model_manager):
        self.config = config
        self.state = state
        self.model_manager = model_manager

        # Detect Google Colab immediately
        self.state.is_colab = "google.colab" in sys.modules
        self.state.host = config.host
        self.state.port = config.port

        self.auth_manager = AuthManager(self.config, self.state)
        self.queue = RequestQueue(self.config, self.state)
        self.tunnel = TunnelManager(self.config, self.state)

        self.app = create_app(
            config=self.config,
            state=self.state,
            auth_manager=self.auth_manager,
            queue=self.queue,
            model_manager=self.model_manager,
        )

        self._server_thread: Optional[threading.Thread] = None
        self._uvicorn_server: Optional[uvicorn.Server] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """
        Starts the API server with a fully verified boot sequence.
        Returns True if the server reached RUNNING state, False otherwise.
        """
        if not self.config.api_enabled:
            logger.info("API is disabled in configuration.", extra={"prefix": "API"})
            return False

        if self.state.api_status == APIStatus.RUNNING:
            logger.info("API is already running.", extra={"prefix": "API"})
            return True

        self._colab_network_check()

        print("\n" + "=" * 44)
        print("  APEX API  —  Starting")
        print("=" * 44)

        # ── Step 1: Launch Uvicorn in background thread ──────────────
        self.state.api_status = APIStatus.STARTING
        print(f"\nLaunching FastAPI on {self.config.host}:{self.config.port}...")
        self._launch_uvicorn()

        # ── Step 2: Wait for the socket to accept connections ────────
        if not self._wait_for_socket():
            self._set_failed("Uvicorn did not bind to the port within the timeout.")
            return False
        print(f"  ✓  Socket bound on port {self.config.port}")

        # ── Step 3: Health check ─────────────────────────────────────
        self.state.api_status = APIStatus.VERIFYING
        print("  Verifying health endpoint...")
        latency = self._wait_for_health()
        if latency is None:
            self._set_failed("Health check did not return HTTP 200 within the timeout.")
            return False
        self.state.health_checked = True
        self.state.last_health_ms = latency
        print(f"  ✓  Health check passed  ({latency:.0f} ms)")

        # ── Step 4: Tunnel ───────────────────────────────────────────
        if self.config.enable_tunnel:
            print(f"  Starting {self.config.tunnel_provider.capitalize()} tunnel...")
            self.tunnel.start()
            public_url = self._wait_for_tunnel()
            if public_url:
                self.state.openai_url = f"{public_url}/v1"
                print(f"  ✓  Tunnel connected:  {public_url}")
            else:
                print("  ✗  Tunnel did not connect within timeout — using local URL.")
        else:
            local_base = f"http://127.0.0.1:{self.config.port}"
            self.state.openai_url = f"{local_base}/v1"

        # ── Step 5: Mark RUNNING ─────────────────────────────────────
        self.state.api_status = APIStatus.RUNNING

        # ── Final Banner ─────────────────────────────────────────────
        auth_str = self.state.authentication
        openai_url = self.state.openai_url or f"http://127.0.0.1:{self.config.port}/v1"

        print("")
        print(f"  Authentication    {auth_str}")
        if self.state.api_key:
            print(f"  API Key           {'*' * 14}")
        print(f"  Tunnel            {'Connected' if self.state.tunnel_connected else 'Disabled'}")
        print(f"  OpenAI Endpoint   {openai_url}")
        print(f"\n  Status            RUNNING")
        print("=" * 44 + "\n")

        logger.info(f"API RUNNING at {openai_url}", extra={"prefix": "SUCCESS"})
        return True

    def stop(self) -> None:
        """Stops the API server and tunnel."""
        self.tunnel.stop()

        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True

        if self._server_thread:
            self._server_thread.join(timeout=5)

        self.state.api_status = APIStatus.STOPPED
        self.state.health_checked = False
        self.state.openai_url = None
        logger.info("API stopped.", extra={"prefix": "SYSTEM"})

    def restart(self) -> bool:
        """Stops and restarts the server."""
        self.stop()
        time.sleep(1)
        return self.start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _colab_network_check(self) -> None:
        """Warns (or blocks) if we are inside Colab without a tunnel."""
        if not self.state.is_colab:
            return
        if self.config.enable_tunnel:
            return
        # Running in Colab without a tunnel — the browser cannot reach 127.0.0.1
        print(
            "\n⚠  WARNING: Running inside Google Colab.\n"
            "   Your browser is on a DIFFERENT machine from this Python process.\n"
            "   http://127.0.0.1:{} will NOT be reachable from your browser.\n"
            "   Set ENABLE_TUNNEL = True and re-run to get a public URL.\n"
            "   The API will still start for in-notebook Python usage.\n".format(self.config.port)
        )

    def _launch_uvicorn(self) -> None:
        """Spawns Uvicorn in a daemon thread."""
        uconfig = uvicorn.Config(
            app=self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="error",
            access_log=False,
        )
        self._uvicorn_server = uvicorn.Server(uconfig)
        self._server_thread = threading.Thread(
            target=self._uvicorn_server.run, daemon=True
        )
        self._server_thread.start()

    def _wait_for_socket(self) -> bool:
        """Polls until the TCP socket is open or timeout expires."""
        deadline = time.time() + _SOCKET_TIMEOUT_S
        host = "127.0.0.1"  # always probe loopback regardless of bind address
        port = self.config.port
        while time.time() < deadline:
            try:
                with socket.create_connection((host, port), timeout=0.5):
                    return True
            except (ConnectionRefusedError, OSError):
                time.sleep(_POLL_INTERVAL_S)
        return False

    def _wait_for_health(self) -> Optional[float]:
        """
        Polls GET /health until HTTP 200 is returned or timeout expires.
        Returns round-trip latency in ms, or None on failure.
        """
        url = f"http://127.0.0.1:{self.config.port}/health"
        deadline = time.time() + _HEALTH_TIMEOUT_S
        while time.time() < deadline:
            try:
                t0 = time.time()
                with urllib.request.urlopen(url, timeout=1) as resp:
                    if resp.status == 200:
                        return (time.time() - t0) * 1000
            except Exception:
                time.sleep(_POLL_INTERVAL_S)
        return None

    def _wait_for_tunnel(self) -> Optional[str]:
        """Waits for the tunnel to populate state.public_url."""
        deadline = time.time() + _TUNNEL_TIMEOUT_S
        while time.time() < deadline:
            if self.state.public_url:
                return self.state.public_url
            time.sleep(_POLL_INTERVAL_S)
        return None

    def _set_failed(self, reason: str) -> None:
        """Marks the API as FAILED and records the error."""
        self.state.api_status = APIStatus.FAILED
        self.state.last_error = reason
        self.state.errors.append(reason)
        print(f"\n  ✗  FAILED: {reason}")
        print("=" * 44 + "\n")
        logger.error(reason, extra={"prefix": "ERROR"})
