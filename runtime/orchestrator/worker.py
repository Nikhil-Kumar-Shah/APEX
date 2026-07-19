"""Background worker thread executing task queue jobs."""

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from runtime.orchestrator.task_queue import Task, TaskQueue
from runtime.orchestrator.events import RuntimeEvent
from runtime.orchestrator.dispatcher import EventDispatcher

logger = logging.getLogger("runtime.orchestrator.worker")


class WorkerThread(threading.Thread):
    """Background execution runner pulling jobs and emitting progress telemetry."""

    def __init__(
        self,
        task_queue: TaskQueue,
        event_dispatcher: EventDispatcher,
        handlers: Dict[str, Callable[[Task], None]]
    ):
        """Initializes the WorkerThread.

        Args:
            task_queue: Central TaskQueue manager.
            event_dispatcher: EventDispatcher registry.
            handlers: Mappings between task_type strings and handler functions.
        """
        super().__init__()
        self.task_queue = task_queue
        self.event_dispatcher = event_dispatcher
        self.handlers = handlers
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Flags the worker thread to stop execution."""
        self._stop_event.set()

    def run(self) -> None:
        """Worker main loop polling tasks."""
        logger.info("[Worker] Thread started.")
        while not self._stop_event.is_set():
            task = self.task_queue.get_next()
            if not task:
                time.sleep(0.1)
                continue

            if task.cancelled:
                task.status = "CANCELLED"
                continue

            # Run Task
            task.status = "RUNNING"
            task.start_time = time.time()
            self.event_dispatcher.publish(RuntimeEvent("task_started", task.to_dict()))

            handler = self.handlers.get(task.task_type)
            if not handler:
                logger.error(f"[Worker] No handler registered for task type: {task.task_type}")
                task.status = "FAILED"
                task.error_message = f"Unsupported task type: {task.task_type}"
                task.completion_time = time.time()
                self.event_dispatcher.publish(RuntimeEvent("task_failed", task.to_dict()))
                continue

            try:
                # Execute Handler
                handler(task)
                if task.status == "RUNNING":
                    task.status = "COMPLETED"
                    task.progress = 100
                    task.completion_time = time.time()
                    self.event_dispatcher.publish(RuntimeEvent("task_finished", task.to_dict()))
            except Exception as e:
                logger.error(f"[Worker] Task execution failed: {e}", exc_info=True)
                task.status = "FAILED"
                task.error_message = str(e)
                task.completion_time = time.time()
                self.event_dispatcher.publish(RuntimeEvent("task_failed", task.to_dict()))

            time.sleep(0.05)
