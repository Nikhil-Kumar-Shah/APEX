"""Connection tracking and stats manager."""

import time
from typing import Any, Dict, Set


class ConnectionManager:
    """Manages active network connections and collects request telemetry statistics."""

    def __init__(self):
        self.active_connections: Set[str] = set()
        self.request_count = 0
        self.start_time = time.time()

    def register_connection(self, client_host: str) -> None:
        """Registers a connection from a client.

        Args:
            client_host: Host/IP identifier of the client.
        """
        self.active_connections.add(client_host)
        self.request_count += 1

    def deregister_connection(self, client_host: str) -> None:
        """Deregisters a connection from a client.

        Args:
            client_host: Host/IP identifier of the client.
        """
        self.active_connections.discard(client_host)

    def get_stats(self) -> Dict[str, Any]:
        """Calculates connection usage and metrics.

        Returns:
            Dict[str, Any]: Uptime, connection count, and total request counts.
        """
        return {
            "active_connections_count": len(self.active_connections),
            "total_requests": self.request_count,
            "uptime_seconds": time.time() - self.start_time,
        }
