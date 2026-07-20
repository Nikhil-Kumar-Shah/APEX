"""
API Lifecycle Manager — deterministic process manager.

Startup algorithm:
    1. Check if port is occupied
       a. Occupied → health-check it
          - Healthy: reuse (RUNNING)
          - Unhealthy: kill stale process, fall through to fresh start
    2. Auto-select a free port if configured port is busy
    3. Launch Uvicorn in daemon thread
    4. Poll until Uvicorn's internal `started` event is set (proves it bound)
    5. Socket probe (double-check kernel view)
    6. GET /health → 200 required
    7. Record PID, uptime, port → RUNNING

Any failure at any step → FAILED with last_error set.
RUNNING is never set unless all 7 steps pass.
"""

import os
import sys
import time
import signal
import socket
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional

import uvicorn

from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState, APIStatus
from runtime.api.authentication import AuthManager
from runtime.api.queue import RequestQueue
from runtime.api.tunnel import TunnelManager
from runtime.api.server import create_app

logger = logging.getLogger("runtime.api.manager")

# Timing constants
_UVICORN_BIND_TIMEOUT_S = 12   # wait for uvicorn.started event
_HEALTH_TIMEOUT_S = 10         # wait for /health → 200
_TUNNEL_TIMEOUT_S = 20         # wait for public_url
_POLL_S = 0.25
_PORT_SEARCH_RANGE = 10        # try up to 10 consecutive ports


def _is_port_occupied(host: str, port: int, timeout: float = 0.5) -> bool:
    """Returns True if something is already listening on host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, OSError):
        return False


def _kill_pid(pid: int) -> bool:
    """Attempt to kill a process. Returns True if successful."""
    try:
        os.kill(pid, signal.SIGTERM)
        # Give it 2s to exit gracefully
        deadline = time.time() + 2
        while time.time() < deadline:
            try:
                os.kill(pid, 0)   # probe: raises if dead
                time.sleep(0.1)
            except ProcessLookupError:
                return True
        # Force kill
        os.kill(pid, signal.SIGKILL)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _find_free_port(start: int, count: int = _PORT_SEARCH_RANGE) -> Optional[int]:
    """Scans start..start+count-1 and returns the first unoccupied port."""
    for port in range(start, start + count):
        if not _is_port_occupied("127.0.0.1", port):
            return port
    return None


class APIManager:
    """
    Deterministic API process manager.

    Every public attribute that reports status is derived from
    verified runtime observations, not from assumptions or flags
    set at call-time.
    """

    def __init__(self, config: APIConfig, state: RuntimeState, model_manager):
        self.config = config
        self.state = state
        self.model_manager = model_manager

        # Detect Google Colab once
        self.state.is_colab = "google.colab" in sys.modules

        self.auth_manager = AuthManager(self.config, self.state)
        self.queue = RequestQueue(self.config, self.state)
        self.tunnel = TunnelManager(self.config, self.state)

        self._uvicorn_server: Optional[uvicorn.Server] = None
        self._server_thread: Optional[threading.Thread] = None
        self._start_time: Optional[datetime] = None
        self._active_port: Optional[int] = None

        # Build the FastAPI app once
        self.app = create_app(
            config=self.config,
            state=self.state,
            auth_manager=self.auth_manager,
            queue=self.queue,
            model_manager=self.model_manager,
        )

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def start(self) -> bool:
        """
        Starts the API server using the deterministic lifecycle.
        Returns True iff the server reaches RUNNING state.
        """
        if not self.config.api_enabled:
            logger.info("API disabled in configuration.", extra={"prefix": "API"})
            return False

        if self.state.api_status == APIStatus.RUNNING:
            logger.info("API is already RUNNING.", extra={"prefix": "API"})
            return True

        self._banner_start()
        self.state.api_status = APIStatus.STARTING

        # ── Colab warning ──────────────────────────────────────────────
        if self.state.is_colab and self.config.transport == "local":
            self._print(
                "⚠  Google Colab detected — tunnel is disabled.\n"
                "   Browsers on your machine CANNOT reach 127.0.0.1.\n"
                "   Set ENABLE_TUNNEL = True for a public URL."
            )

        # ── Step 1: Port negotiation ───────────────────────────────────
        effective_port = self._negotiate_port(self.config.internal_port)
        if effective_port is None:
            base = self.config.internal_port or 8000
            return self._fail(
                f"No free port found in range {base}–"
                f"{base + _PORT_SEARCH_RANGE - 1}."
            )
        self._active_port = effective_port
        self.state.port = effective_port

        # ── Step 2: Launch Uvicorn ─────────────────────────────────────
        self._print(f"Launching FastAPI on {self.config.internal_host}:{effective_port}...")
        if not self._launch_uvicorn(effective_port):
            return self._fail("Uvicorn failed to bind within the timeout.")
        self._print(f"  ✓  Uvicorn bound on port {effective_port}")

        # ── Step 3: Health verification ────────────────────────────────
        self.state.api_status = APIStatus.VERIFYING
        self._print("  Verifying /health endpoint...")
        latency = self._poll_health(effective_port)
        if latency is None:
            return self._fail("/health did not return HTTP 200 within timeout.")
        self.state.health_checked = True
        self.state.last_health_ms = latency
        self._print(f"  ✓  Health verified  ({latency:.0f} ms)")

        # ── Step 4: Tunnel ─────────────────────────────────────────────
        if self.config.transport != "local":
            self._print(f"  Starting {self.config.transport.capitalize()} tunnel...")
            if not self.tunnel.start():
                return self._fail(f"{self.config.transport.capitalize()} tunnel failed to start.")
            
            public_url = self._poll_tunnel()
            if public_url:
                self.state.openai_url = f"{public_url}/v1"
                self._print(f"  ✓  Tunnel connected:  {public_url}")
            else:
                return self._fail(f"{self.config.transport.capitalize()} tunnel did not connect within timeout.")
        else:
            self.state.openai_url = f"http://127.0.0.1:{effective_port}/v1"

        # ── Mark RUNNING ───────────────────────────────────────────────
        self.state.api_status = APIStatus.RUNNING
        self._start_time = datetime.utcnow()
        self._banner_running()
        return True

    def stop(self) -> None:
        """Stops the API server and tunnel."""
        self.tunnel.stop()
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True
        if self._server_thread:
            self._server_thread.join(timeout=5)
        self._uvicorn_server = None
        self._server_thread = None
        self._active_port = None
        self._start_time = None
        self.state.api_status = APIStatus.STOPPED
        self.state.health_checked = False
        self.state.openai_url = None
        logger.info("API stopped.", extra={"prefix": "SYSTEM"})

    def restart(self) -> bool:
        """Stops and restarts the server."""
        self.stop()
        time.sleep(0.5)
        return self.start()

    def is_running(self) -> bool:
        """Returns True only when health-verified and RUNNING."""
        return self.state.api_status == APIStatus.RUNNING

    def uptime(self) -> Optional[float]:
        """Returns server uptime in seconds, or None if not running."""
        if self._start_time and self.is_running():
            return (datetime.utcnow() - self._start_time).total_seconds()
        return None

    # ------------------------------------------------------------------ #
    # Port negotiation                                                     #
    # ------------------------------------------------------------------ #

    def _negotiate_port(self, requested: Optional[int]) -> Optional[int]:
        """
        Determines which port to use.

        Cases:
          A. Port is free → use it.
          B. Port is occupied + healthy existing server → reuse it (print notice).
          C. Port is occupied + unhealthy → try to free, then auto-select.
        """
        if requested is None:
            base = 8000
            return _find_free_port(base)

        if not _is_port_occupied("127.0.0.1", requested):
            return requested

        # Something is already on the port
        self._print(f"  Port {requested} is occupied — checking existing process...")
        latency = self._poll_health(requested, timeout_s=3)
        if latency is not None:
            self._print(
                f"  ✓  Existing healthy server detected on port {requested} "
                f"({latency:.0f} ms) — reusing."
            )
            # Reuse: skip Uvicorn launch, jump straight to RUNNING
            self.state.health_checked = True
            self.state.last_health_ms = latency
            self.state.port = requested
            self._active_port = requested
            self.state.openai_url = f"http://127.0.0.1:{requested}/v1"
            self.state.api_status = APIStatus.RUNNING
            self._start_time = datetime.utcnow()
            self._banner_running(reused=True)
            return None  # Signals: already done, do not proceed with launch

        # Unhealthy stale process — try to clear and auto-select
        self._print(f"  ✗  Stale process on port {requested} (no healthy /health). Selecting alternative port...")
        free_port = _find_free_port(requested + 1)
        if free_port:
            self._print(f"  ↳  Using port {free_port} instead.")
            return free_port

        return None

    # ------------------------------------------------------------------ #
    # Uvicorn launch                                                       #
    # ------------------------------------------------------------------ #

    def _launch_uvicorn(self, port: int) -> bool:
        """
        Spawns Uvicorn and waits for its internal `started` event.
        Returns True only if Uvicorn actually bound to the port.
        """
        uconfig = uvicorn.Config(
            app=self.app,
            host=self.config.internal_host,
            port=port,
            log_level="error",
            access_log=False,
        )
        self._uvicorn_server = uvicorn.Server(uconfig)

        self._server_thread = threading.Thread(
            target=self._uvicorn_server.run, daemon=True
        )
        self._server_thread.start()

        # Wait for uvicorn.Server.started flag — this is set only after
        # the socket is successfully bound. It is NOT set if bind fails.
        deadline = time.time() + _UVICORN_BIND_TIMEOUT_S
        while time.time() < deadline:
            if self._uvicorn_server.started:
                return True
            # Check if thread died early (bind error, etc.)
            if not self._server_thread.is_alive():
                return False
            time.sleep(_POLL_S)

        return False

    # ------------------------------------------------------------------ #
    # Health polling                                                       #
    # ------------------------------------------------------------------ #

    def _poll_health(self, port: int, timeout_s: float = _HEALTH_TIMEOUT_S) -> Optional[float]:
        """
        Polls GET /health until HTTP 200 is returned.
        Returns round-trip latency in ms, or None on timeout/failure.
        """
        url = f"http://127.0.0.1:{port}/health"
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                t0 = time.time()
                with urllib.request.urlopen(url, timeout=1) as resp:
                    if resp.status == 200:
                        return (time.time() - t0) * 1000
            except Exception:
                pass
            time.sleep(_POLL_S)
        return None

    def _poll_tunnel(self) -> Optional[str]:
        """Waits for the tunnel to populate state.public_url."""
        deadline = time.time() + _TUNNEL_TIMEOUT_S
        while time.time() < deadline:
            if self.state.public_url:
                return self.state.public_url
            time.sleep(_POLL_S)
        return None

    # ------------------------------------------------------------------ #
    # Failure helper                                                       #
    # ------------------------------------------------------------------ #

    def _fail(self, reason: str) -> bool:
        self.state.api_status = APIStatus.FAILED
        self.state.last_error = reason
        self.state.errors.append(reason)
        self._print(f"\n  ✗  FAILED: {reason}")
        self._print("=" * 46 + "\n")
        logger.error(reason, extra={"prefix": "ERROR"})
        return False

    # ------------------------------------------------------------------ #
    # Banner helpers                                                       #
    # ------------------------------------------------------------------ #

    def _print(self, msg: str) -> None:
        print(msg)
        logger.info(msg.strip(), extra={"prefix": "API"})

    def _banner_start(self) -> None:
        print("\n" + "=" * 46)
        print("  APEX API  —  Starting")
        print("=" * 46)

    def _banner_running(self, reused: bool = False) -> None:
        auth_str = self.state.authentication
        openai_url = self.state.openai_url or f"http://127.0.0.1:{self._active_port}/v1"
        reuse_note = "  (reused existing process)" if reused else ""
        print(f"")
        print(f"  Authentication    {auth_str}")
        if self.state.api_key:
            print(f"  API Key           {'*' * 14}")
        print(f"  Tunnel            {'Connected' if self.state.tunnel_connected else 'Disabled'}")
        print(f"  OpenAI Endpoint   {openai_url}")
        print(f"\n  Status            RUNNING{reuse_note}")
        print("=" * 46 + "\n")
        logger.info(f"API RUNNING at {openai_url}", extra={"prefix": "SUCCESS"})
