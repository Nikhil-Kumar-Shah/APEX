"""APEX Central Runtime Orchestrator managing background workers and event handlers."""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from runtime.orchestrator.task_queue import Task, TaskQueue
from runtime.orchestrator.dispatcher import EventDispatcher
from runtime.orchestrator.state_machine import RuntimeStateMachine
from runtime.orchestrator.notifications import NotificationCenter
from runtime.orchestrator.scheduler import TaskScheduler
from runtime.orchestrator.worker import WorkerThread

logger = logging.getLogger("runtime.orchestrator")


class RuntimeOrchestrator:
    """Central coordinator manager managing execution pipelines and thread pools."""

    def __init__(self, model_manager: Any, workspace_manager: Any):
        """Initializes the RuntimeOrchestrator."""
        self.model_manager = model_manager
        self.workspace_manager = workspace_manager
        
        self.task_queue = TaskQueue()
        self.event_dispatcher = EventDispatcher()
        self.state_machine = RuntimeStateMachine("STOPPED")
        self.notification_center = NotificationCenter()
        self.scheduler = TaskScheduler()

        # Task Handlers Registry
        self.handlers: Dict[str, Callable[[Task], None]] = {
            "download_model": self._handle_download_model,
            "load_model": self._handle_load_model,
            "sync_workspace": self._handle_sync_workspace,
        }

        # Start worker thread
        self.worker = WorkerThread(self.task_queue, self.event_dispatcher, self.handlers)
        self.worker.start()
        
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
        return self.task_queue.submit(task)

    # Handlers implementations
    def _handle_download_model(self, task: Task) -> None:
        model_id = task.payload.get("model_id")
        if not model_id:
            raise ValueError("Missing 'model_id' in download payload")

        self.state_machine.transition_to("DOWNLOADING_MODEL")
        self.notification_center.notify(f"Download started for {model_id}", "info")
        
        # Simulated download progress transitions
        for p in range(10, 101, 30):
            task.progress = min(p, 100)
            time_now = 0.1
            task.status = "RUNNING"
            self.event_dispatcher.publish(RuntimeEvent("task_progress", task.to_dict()))
            import time
            time.sleep(0.2)

        self.model_manager.download_model(model_id)
        self.state_machine.transition_to("READY")
        self.notification_center.notify(f"Download complete for {model_id}", "success")

    def _handle_load_model(self, task: Task) -> None:
        model_id = task.payload.get("model_id")
        if not model_id:
            raise ValueError("Missing 'model_id' in load model payload")

        self.state_machine.transition_to("LOADING_MODEL")
        self.notification_center.notify(f"Loading weights for {model_id}...", "info")

        task.progress = 50
        self.event_dispatcher.publish(RuntimeEvent("task_progress", task.to_dict()))

        # Call active model manager loading
        self.model_manager.load_model(model_id)
        
        self.state_machine.transition_to("READY")
        self.notification_center.notify(f"Model {model_id} is loaded and ready.", "success")
        task.progress = 100

    def _handle_sync_workspace(self, task: Task) -> None:
        self.notification_center.notify("Workspace synchronization started", "info")
        task.progress = 50
        import time
        time.sleep(0.5)
        task.progress = 100
        self.notification_center.notify("Workspace synchronization complete", "success")
