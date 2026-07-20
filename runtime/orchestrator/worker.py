"""Background worker thread executing task queue jobs — APEX V1."""

import logging
import threading
import time
import traceback
import sys
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
        logger.info("Worker thread started.", extra={"prefix": "WORKER"})
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
                logger.info(f"Task {task.task_id} cancelled by user.", extra={"prefix": "WORKER"})
                continue

            # Run Task
            task.update_status("PREPARING", progress=10)
            task.start_time = time.time()
            self.event_dispatcher.publish(RuntimeEvent("task_started", task.to_dict()))
            logger.info(f"Preparing task: {task.task_type}", extra={"prefix": "WORKER"})

            handler = self.handlers.get(task.task_type)
            if not handler:
                logger.error(f"No handler registered for task type: {task.task_type}", extra={"prefix": "ERROR"})
                task.update_status("FAILED")
                task.error_message = f"Unsupported task type: {task.task_type}"
                task.completion_time = time.time()
                self.event_dispatcher.publish(RuntimeEvent("task_failed", task.to_dict()))
                continue

            try:
                handler(task)
                
                # If the handler successfully finished and didn't fail it
                if task.status != "FAILED":
                    task.update_status("READY", progress=100)
                    task.completion_time = time.time()
                    self.event_dispatcher.publish(RuntimeEvent("task_finished", task.to_dict()))
                    logger.info(f"Task completed: {task.task_type}", extra={"prefix": "SUCCESS"})
            except Exception as e:
                # Structured error reporting with full context
                task.update_status("FAILED")
                task.error_message = str(e)
                task.completion_time = time.time()

                # Extract traceback location
                tb = traceback.extract_tb(sys.exc_info()[2])
                if tb:
                    last_frame = tb[-1]
                    location = f"{last_frame.filename}:{last_frame.lineno}"
                    func_name = last_frame.name
                else:
                    location = "unknown"
                    func_name = "unknown"

                logger.error(
                    f"Task: {task.task_type}\n"
                    f"  Reason: {type(e).__name__}: {e}\n"
                    f"  Location: {location}\n"
                    f"  Function: {func_name}\n"
                    f"  Task cancelled. State restored to READY.",
                    extra={"prefix": "ERROR"},
                )

                # Restore state machine
                try:
                    self.orchestrator.state_machine.transition_to("READY")
                except Exception:
                    pass

                self.event_dispatcher.publish(RuntimeEvent("task_failed", task.to_dict()))

            time.sleep(0.05)
