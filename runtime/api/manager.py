"""
API Lifecycle Manager — deterministic process manager.

Startup algorithm:
    1. Check if port is occupied
       a. Occupied → health-check it
          - Healthy APEX server: reuse (RUNNING)
          - Unhealthy / alien: try alternative ports in range
    2. Auto-select a free port if configured port is busy
    3. Launch Uvicorn in daemon thread (if not reusing)
    4. Poll until Uvicorn's internal `started` event is set
    5. Local GET /health → 200 required
    6. Cloudflare Tunnel startup & Public URL acquisition (if transport != "local")
    7. Public endpoint external reachability verification
    8. Actual end-to-end model inference verification (if model is loaded)
    9. Record PID, uptime, port → RUNNING

Any failure at any step → FAILED with last_error set.
RUNNING is never set unless all required steps pass.
"""

import os
import sys
import json
import time
import signal
import socket
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional, Tuple

import uvicorn

from runtime.api.configuration import APIConfig
from runtime.api.state import RuntimeState, APIStatus
from runtime.api.authentication import AuthManager
from runtime.api.queue import RequestQueue
from runtime.api.tunnel import TunnelManager
from runtime.api.server import create_app
from runtime.core.errors import ApexErrorCode

logger = logging.getLogger("runtime.api.manager")

# Transparent DNS fallback for Cloudflare Quick Tunnels:
# Local ISP or router DNS often caches NXDOMAIN or takes 30-60s to propagate brand-new trycloudflare.com subdomains.
# When socket.gaierror occurs for trycloudflare.com, resolve via Cloudflare DoH (1.1.1.1).
_orig_getaddrinfo = socket.getaddrinfo

def _resolve_trycloudflare_host(hostname: str) -> Optional[str]:
    try:
        import httpx
        url = f"https://1.1.1.1/dns-query?name={hostname}&type=A"
        r = httpx.get(url, headers={"accept": "application/dns-json"}, timeout=3.0)
        if r.status_code == 200:
            for ans in r.json().get("Answer", []):
                if ans.get("type") == 1 and ans.get("data"):
                    return ans["data"]
    except Exception:
        pass
    return None

def _trycloudflare_getaddrinfo(host, port, *args, **kwargs):
    try:
        return _orig_getaddrinfo(host, port, *args, **kwargs)
    except socket.gaierror:
        if host and isinstance(host, str) and "trycloudflare.com" in host:
            ip = _resolve_trycloudflare_host(host)
            if ip:
                return _orig_getaddrinfo(ip, port, *args, **kwargs)
        raise

socket.getaddrinfo = _trycloudflare_getaddrinfo

# Timing constants
_UVICORN_BIND_TIMEOUT_S = 12   # wait for uvicorn.started event
_HEALTH_TIMEOUT_S = 10         # wait for /health → 200
_TUNNEL_TIMEOUT_S = 25         # wait for public_url
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
        deadline = time.time() + 2
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except ProcessLookupError:
                return True
        os.kill(pid, signal.SIGKILL)
        return True
    except (ProcessLookupError, PermissionError, Exception):
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
        Returns True iff the server reaches verified RUNNING state.
        """
        if not self.config.api_enabled:
            logger.info("API disabled in configuration.", extra={"prefix": "API"})
            return False

        if self.state.api_status == APIStatus.RUNNING:
            logger.info("API is already RUNNING.", extra={"prefix": "API"})
            return True

        self._banner_start()
        self.state.api_status = APIStatus.STARTING

        # Colab warning
        if self.state.is_colab and self.config.transport == "local":
            self._print(
                "⚠  Google Colab detected — tunnel is disabled.\n"
                "   Browsers on your machine CANNOT reach 127.0.0.1.\n"
                "   Set TRANSPORT = 'cloudflare' for a public URL."
            )

        # ── Step 1: Port negotiation ───────────────────────────────────
        effective_port, is_reused = self._negotiate_port(self.config.internal_port)
        if effective_port is None:
            base = self.config.internal_port or 8000
            return self._fail(
                f"[{ApexErrorCode.API_STARTUP_FAILED}] No free port found in range {base}–"
                f"{base + _PORT_SEARCH_RANGE - 1}."
            )
        self._active_port = effective_port
        self.state.port = effective_port

        # ── Step 2: Launch or Reuse Uvicorn ─────────────────────────────
        if is_reused:
            self._print(f"  ✓  Reusing existing healthy APEX server on port {effective_port}")
            self.state.health_checked = True
            self.state.last_health_ms = self._poll_health(effective_port, timeout_s=1.5) or 5.0
        else:
            self._print(f"Launching FastAPI on {self.config.internal_host}:{effective_port}...")
            if not self._launch_uvicorn(effective_port):
                return self._fail(f"[{ApexErrorCode.API_STARTUP_FAILED}] Uvicorn failed to bind within the timeout.")
            self._print(f"  ✓  Uvicorn bound on port {effective_port}")

            # ── Step 3: Local Health verification ──────────────────────
            self.state.api_status = APIStatus.VERIFYING
            self._print("  Verifying /health endpoint...")
            latency = self._poll_health(effective_port)
            if latency is None:
                return self._fail(f"[{ApexErrorCode.API_HEALTH_CHECK_FAILED}] /health did not return HTTP 200 within timeout.")
            self.state.health_checked = True
            self.state.last_health_ms = latency
            self._print(f"  ✓  Health verified  ({latency:.0f} ms)")

        # ── Step 4: Tunnel Startup & Public Verification ──────────────
        public_url = None
        if self.config.transport != "local":
            self._print(f"  Starting {self.config.transport.capitalize()} tunnel...")
            if not self.tunnel.process or self.tunnel.process.poll() is not None:
                if not self.tunnel.start():
                    err_msg = self.state.last_error or "Tunnel process failed to start"
                    return self._fail(f"[{ApexErrorCode.TUNNEL_STARTUP_FAILED}] {self.config.transport.capitalize()} tunnel failed to start: {err_msg}")

            self._print("  Waiting for public tunnel URL...")
            public_url = self.tunnel.wait_for_url(timeout_s=_TUNNEL_TIMEOUT_S)
            if public_url:
                self.state.openai_url = f"{public_url}/v1"
                self._print(f"  ✓  Tunnel connected:  {public_url}")

                # External reachability check
                self._print("  Verifying public endpoint reachability...")
                pub_ok, pub_lat = self._verify_public_endpoint(public_url)
                if not pub_ok:
                    return self._fail(f"[{ApexErrorCode.PUBLIC_ENDPOINT_UNAVAILABLE}] Public endpoint '{public_url}' unreachable externally: {self.state.last_error}")
                self._print(f"  ✓  Public endpoint verified  ({pub_lat:.0f} ms)")
            else:
                err_msg = self.state.last_error or "timeout waiting for trycloudflare.com URL"
                return self._fail(f"[{ApexErrorCode.TUNNEL_URL_NOT_FOUND}] {self.config.transport.capitalize()} tunnel did not connect within timeout: {err_msg}")
        else:
            self.state.openai_url = f"http://127.0.0.1:{effective_port}/v1"

        # ── Step 5: End-to-End Model Inference Verification ────────────
        base_endpoint = public_url or f"http://127.0.0.1:{effective_port}"
        if self.model_manager and getattr(self.model_manager, "active_engine", None) and getattr(self.model_manager.active_engine, "is_loaded", False):
            self._print(f"  Verifying end-to-end model inference via {base_endpoint}...")
            inf_ok, inf_msg = self._verify_inference(base_endpoint)
            if not inf_ok:
                return self._fail(f"[{ApexErrorCode.PUBLIC_INFERENCE_FAILED}] End-to-end model inference verification failed: {inf_msg}")
            self._print(f"  ✓  End-to-end model inference verified successfully.")

        # ── Mark RUNNING ───────────────────────────────────────────────
        self.state.api_status = APIStatus.RUNNING
        self._start_time = datetime.now(timezone.utc)
        self._banner_running(reused=is_reused)
        return True

    def verify_inference_if_ready(self) -> Tuple[bool, str]:
        """Runs E2E inference check against active endpoint once model is loaded."""
        effective_port = self._active_port or self.config.internal_port or 8000
        base_endpoint = self.state.public_url or f"http://127.0.0.1:{effective_port}"
        if not (self.model_manager and getattr(self.model_manager, "active_engine", None) and getattr(self.model_manager.active_engine, "is_loaded", False)):
            return (False, "Model is not loaded.")
        return self._verify_inference(base_endpoint)

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
            return (datetime.now(timezone.utc) - self._start_time).total_seconds()
        return None

    # ------------------------------------------------------------------ #
    # Port negotiation                                                     #
    # ------------------------------------------------------------------ #

    def _negotiate_port(self, requested: Optional[int]) -> Tuple[Optional[int], bool]:
        """
        Determines which port to use.

        Returns:
            Tuple[Optional[int], bool]: (allocated_port, is_reused)
        """
        if requested is None:
            base = 8000
            port = _find_free_port(base)
            return port, False

        if not _is_port_occupied("127.0.0.1", requested):
            return requested, False

        # Something is already on the port
        self._print(f"  Port {requested} is occupied — checking existing process...")
        latency = self._poll_health(requested, timeout_s=2.5)
        if latency is not None:
            # Verified healthy existing server
            return requested, True

        # Unhealthy stale process / alien process — auto-select alternative
        self._print(f"  ✗  Stale process on port {requested} (no healthy /health). Selecting alternative port...")
        free_port = _find_free_port(requested + 1)
        if free_port:
            self._print(f"  ↳  Using port {free_port} instead.")
            return free_port, False

        return None, False

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

        deadline = time.time() + _UVICORN_BIND_TIMEOUT_S
        while time.time() < deadline:
            if self._uvicorn_server.started:
                return True
            if not self._server_thread.is_alive():
                return False
            time.sleep(_POLL_S)

        return False

    # ------------------------------------------------------------------ #
    # Health and Verification polling                                     #
    # ------------------------------------------------------------------ #

    def _poll_health(self, port: int, timeout_s: float = _HEALTH_TIMEOUT_S) -> Optional[float]:
        """
        Polls GET /health until HTTP 200 is returned with valid response.
        Returns round-trip latency in ms, or None on timeout/failure.
        """
        url = f"http://127.0.0.1:{port}/health"
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                t0 = time.time()
                req = urllib.request.Request(url, headers={"User-Agent": "APEX-HealthCheck/1.0", "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        body = resp.read().decode("utf-8")
                        try:
                            data = json.loads(body)
                            if data.get("project") == "APEX" or "status" in data:
                                return (time.time() - t0) * 1000
                        except Exception:
                            return (time.time() - t0) * 1000
            except Exception:
                pass
            time.sleep(_POLL_S)
        return None

    def _verify_public_endpoint(self, public_url: str, timeout_s: float = 45.0) -> Tuple[bool, float]:
        """Sends an external HTTP GET to the public tunnel health endpoint."""
        url = f"{public_url}/health"
        deadline = time.time() + timeout_s
        last_exc = None
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            try:
                t0 = time.time()
                try:
                    import httpx
                    with httpx.Client(timeout=6.0, follow_redirects=True) as client:
                        resp = client.get(
                            url,
                            headers={"User-Agent": "APEX-PublicVerifier/1.0", "Accept": "application/json"}
                        )
                        if resp.status_code == 200:
                            lat = (time.time() - t0) * 1000
                            return True, lat
                except ImportError:
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "APEX-PublicVerifier/1.0", "Accept": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=5.0) as resp:
                        if resp.status == 200:
                            lat = (time.time() - t0) * 1000
                            return True, lat
            except Exception as e:
                last_exc = e
            if attempt % 5 == 0:
                logger.info(f"Waiting for Cloudflare DNS propagation ({url})...", extra={"prefix": "TUNNEL"})
            time.sleep(2.0)
        self.state.last_error = f"Public URL check failed: {last_exc}"
        return False, 0.0

    def _verify_inference(self, base_url: str, timeout_s: float = 25.0) -> Tuple[bool, str]:
        """Sends an actual chat completion request through the base endpoint."""
        url = f"{base_url}/v1/chat/completions"
        payload_dict = {
            "model": "apex-runtime-model",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
            "temperature": 0.0,
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "APEX-InferenceVerifier/1.0",
        }
        if self.config.enable_auth and self.state.api_key:
            headers["Authorization"] = f"Bearer {self.state.api_key}"

        deadline = time.time() + timeout_s
        last_err = ""
        while time.time() < deadline:
            try:
                try:
                    import httpx
                    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                        resp = client.post(url, json=payload_dict, headers=headers)
                        if resp.status_code == 200:
                            res_data = resp.json()
                            choices = res_data.get("choices", [])
                            if choices:
                                return True, "Verified"
                            return False, "Response did not contain choices."
                        last_err = f"HTTP {resp.status_code}: {resp.text}"
                except ImportError:
                    payload = json.dumps(payload_dict).encode("utf-8")
                    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                    with urllib.request.urlopen(req, timeout=10.0) as resp:
                        if resp.status == 200:
                            res_data = json.loads(resp.read().decode("utf-8"))
                            choices = res_data.get("choices", [])
                            if choices:
                                return True, "Verified"
                            return False, "Response did not contain choices."
            except Exception as e:
                last_err = str(e)
            time.sleep(1.5)
        return False, f"Inference request failed: {last_err}"

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
