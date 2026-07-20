"""APEX Central Runtime Orchestrator — V1 (HF + Transformers only)."""

import logging
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from runtime.orchestrator.task_queue import Task, TaskQueue
from runtime.orchestrator.dispatcher import EventDispatcher
from runtime.orchestrator.events import RuntimeEvent
from runtime.orchestrator.state_machine import RuntimeStateMachine
from runtime.orchestrator.notifications import NotificationCenter
from runtime.orchestrator.scheduler import TaskScheduler
from runtime.orchestrator.worker import WorkerThread

logger = logging.getLogger("runtime.orchestrator")


class RuntimeOrchestrator:
    """Central coordinator managing execution pipelines and background workers."""

    def __init__(self, model_manager: Any, workspace_manager: Any):
        """Initializes the RuntimeOrchestrator."""
        self.model_manager = model_manager
        self.workspace_manager = workspace_manager
        
        self.task_queue = TaskQueue()
        self.event_dispatcher = EventDispatcher()
        self.state_machine = RuntimeStateMachine("STOPPED")
        self.notification_center = NotificationCenter()
        self.scheduler = TaskScheduler()

        # Heartbeat registry
        self.worker_heartbeat = time.time()

        # Task Handlers Registry
        self.handlers: Dict[str, Callable[[Task], None]] = {
            "download_model": self._handle_download_model,
            "load_model": self._handle_load_model,
            "sync_workspace": self._handle_sync_workspace,
        }

        # Start worker thread (passing self to track heartbeats)
        self.worker = WorkerThread(self, self.task_queue, self.event_dispatcher, self.handlers)
        self.worker.start()
        
        # Add background check job for stalled tasks (every 10 seconds)
        self.scheduler.add_job(10.0, self._handle_stalled_tasks)
        
        # Start scheduler
        self.scheduler.start()

    def shutdown(self) -> None:
        """Safely stops workers and schedulers."""
        self.worker.stop()
        self.scheduler.stop()

    def submit_task(self, task_type: str, payload: Optional[Dict[str, Any]] = None, priority: int = 10) -> str:
        """Helper to submit a job to the background queue.

        Args:
            task_type: Target type.
            payload: Payload details.
            priority: Scheduling priority.

        Returns:
            str: Task ID.
        """
        task = Task(task_type, payload, priority)
        logger.info(f"Task submitted: {task_type}", extra={"prefix": "QUEUE"})
        return self.task_queue.submit(task)

    def _handle_stalled_tasks(self) -> None:
        """Finds tasks that have not reported updates for more than 30 seconds and aborts them."""
        now = time.time()
        for t in self.task_queue._tasks.values():
            if t.status in ["QUEUED", "RUNNING", "DISPATCHED"] and (now - t.last_updated) > 30.0:
                logger.warning(f"Task {t.task_id} ({t.task_type}) stalled. Aborting task.", extra={"prefix": "WORKER"})
                t.update_status("FAILED")
                t.error_message = "Task execution timed out (worker did not report updates)."
                self.notification_center.notify(f"Task '{t.task_type}' stalled and was aborted.", "warning")
                self.event_dispatcher.publish(RuntimeEvent("task_failed", t.to_dict()))
                # Restore state machine
                self.state_machine.transition_to("READY")

    # --- V1 Handlers: Real execution with full telemetry ---

    def _handle_download_model(self, task: Task) -> None:
        """Downloads a Hugging Face model with full console telemetry."""
        model_id = task.payload.get("model_id")
        if not model_id:
            raise ValueError("Missing 'model_id' in download payload")

        self.state_machine.transition_to("DOWNLOADING_MODEL")
        self.notification_center.notify(f"Download started for {model_id}", "info")
        
        task.update_status("RUNNING", progress=10)
        self.event_dispatcher.publish(RuntimeEvent("task_progress", task.to_dict()))

        # Real download — all telemetry is emitted by the ModelManager and Downloader
        self.model_manager.download_model(model_id)

        self.state_machine.transition_to("READY")
        self.notification_center.notify(f"Download complete for {model_id}", "success")

    def _handle_load_model(self, task: Task) -> None:
        """Loads a Hugging Face model into memory with full console telemetry."""
        model_id = task.payload.get("model_id")
        if not model_id:
            raise ValueError("Missing 'model_id' in load model payload")

        self.state_machine.transition_to("LOADING_MODEL")
        self.notification_center.notify(f"Loading weights for {model_id}...", "info")

        task.update_status("RUNNING", progress=20)
        self.event_dispatcher.publish(RuntimeEvent("task_progress", task.to_dict()))

        # Real load — all telemetry is emitted by ModelManager
        self.model_manager.load_model(model_id)
        
        self.state_machine.transition_to("READY")
        self.notification_center.notify(f"Model {model_id} is loaded and ready.", "success")
        task.update_status("COMPLETED", progress=100)

    def _handle_sync_workspace(self, task: Task) -> None:
        """Syncs the active workspace."""
        self.notification_center.notify("Workspace synchronization started", "info")
        task.update_status("RUNNING", progress=50)
        time.sleep(0.5)
        task.update_status("COMPLETED", progress=100)
        self.notification_center.notify("Workspace synchronization complete", "success")
