"""Periodic task scheduling engine."""

import threading
import time
from typing import Callable, List, Tuple


class TaskScheduler:
    """Invokes recurring health diagnostics checks or task cleanups."""

    def __init__(self):
        self._jobs: List[Tuple[float, Callable[[], None], float]] = [] # (interval, callback, last_run)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def add_job(self, interval_seconds: float, callback: Callable[[], None]) -> None:
        """Schedules a recurring background callback."""
        self._jobs.append((interval_seconds, callback, time.time()))

    def start(self) -> None:
        """Starts the background scheduler thread loop."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stops the scheduler thread."""
        self._stop_event.set()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            now = time.time()
            for i, (interval, cb, last_run) in enumerate(self._jobs):
                if now - last_run >= interval:
                    try:
                        cb()
                    except Exception:
                        pass
                    # Update last run
                    self._jobs[i] = (interval, cb, now)
            time.sleep(0.5)
