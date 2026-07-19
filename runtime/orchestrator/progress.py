"""Helper calculators for processing progress increments and ETAs."""

import time
from typing import Dict, Any

class ProgressTracker:
    """Computes download speeds, ETA estimations, and remaining file payload sizes."""

    @staticmethod
    def calculate_eta(
        bytes_transferred: int,
        total_bytes: int,
        start_time: float
    ) -> Dict[str, Any]:
        """Calculates download speed and estimated time of completion.

        Args:
            bytes_transferred: Downloaded size.
            total_bytes: Total file size.
            start_time: Timestamp of download start.

        Returns:
            Dict[str, Any]: Computed metrics.
        """
        elapsed = time.time() - start_time
        if elapsed <= 0 or bytes_transferred <= 0:
            return {
                "speed_mbps": 0.0,
                "eta_sec": 0.0,
                "percentage": 0.0
            }

        speed = bytes_transferred / elapsed  # bytes/sec
        remaining_bytes = max(0, total_bytes - bytes_transferred)
        eta = remaining_bytes / speed if speed > 0 else 0.0
        percentage = (bytes_transferred / total_bytes) * 100.0 if total_bytes > 0 else 0.0

        return {
            "speed_mbps": speed / (1024 * 1024),
            "eta_sec": eta,
            "percentage": percentage
        }
