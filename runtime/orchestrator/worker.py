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
        orchestrator: Any,
        task_queue: TaskQueue,
        event_dispatcher: EventDispatcher,
        handlers: Dict[str, Callable[[Task], None]]
    ):
        """Initializes the WorkerThread.

        Args:
            orchestrator: The parent RuntimeOrchestrator instance.
            task_queue: Central TaskQueue manager.
            event_dispatcher: EventDispatcher registry.
            handlers: Mappings between task_type strings and handler functions.
        """
        super().__init__()
        self.orchestrator = orchestrator
        self.task_queue = task_queue
        self.event_dispatcher = event_dispatcher
        self.handlers = handlers
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Flags the worker thread to stop execution."""
        self._stop_event.set()

    def run(self) -> None:
        """Worker main loop polling tasks and updating heartbeats."""
        logger.info("[Worker] Thread started.")
        while not self._stop_event.is_set():
            # Update Heartbeat
            self.orchestrator.worker_heartbeat = time.time()

            task = self.task_queue.get_next()
            if not task:
                time.sleep(0.1)
                continue

            if task.cancelled:
                task.update_status("FAILED")
                task.error_message = "Task cancelled by user."
                continue

            # Run Task
            task.update_status("PREPARING", progress=10)
            task.start_time = time.time()
            self.event_dispatcher.publish(RuntimeEvent("task_started", task.to_dict()))

            handler = self.handlers.get(task.task_type)
            if not handler:
                logger.error(f"[Worker] No handler registered for task type: {task.task_type}")
                task.update_status("FAILED")
                task.error_message = f"Unsupported task type: {task.task_type}"
                task.completion_time = time.time()
                self.event_dispatcher.publish(RuntimeEvent("task_failed", task.to_dict()))
                continue

            try:
                # The handler itself is responsible for emitting granular lifecycle events:
                # DOWNLOADING -> VERIFYING -> LOADING TOKENIZER -> INITIALIZING MODEL -> MOVING TO GPU
                handler(task)
                
                # If the handler successfully finished and didn't fail it
                if task.status != "FAILED":
                    task.update_status("READY", progress=100)
                    task.completion_time = time.time()
                    self.event_dispatcher.publish(RuntimeEvent("task_finished", task.to_dict()))
            except Exception as e:
                logger.error(f"[Worker] Task execution failed: {e}", exc_info=True)
                task.update_status("FAILED")
                task.error_message = str(e)
                task.completion_time = time.time()
                self.event_dispatcher.publish(RuntimeEvent("task_failed", task.to_dict()))

            time.sleep(0.05)
