"""Thread-safe task queue managing queued, active, and completed jobs."""

import queue
import time
import uuid
from typing import Any, Dict, List, Optional


class Task:
    """Represents a background execution job with detailed lifecycle transitions."""

    LIFECYCLE_STATES = [
        "QUEUED",
        "VALIDATING",
        "DISPATCHED",
        "STARTING",
        "RUNNING",
        "FINALIZING",
        "COMPLETED",
        "FAILED",
    ]

    def __init__(self, task_type: str, payload: Optional[Dict[str, Any]] = None, priority: int = 10):
        """Initializes the Task."""
        self.task_id = str(uuid.uuid4())
        self.task_type = task_type
        self.payload = payload or {}
        self.priority = priority
        self.status = "QUEUED"
        self.progress = 0
        self.created_at = time.time()
        self.last_updated = time.time()
        self.start_time: Optional[float] = None
        self.completion_time: Optional[float] = None
        self.error_message: Optional[str] = None
        self.cancelled = False

    def update_status(self, new_status: str, progress: int = 0) -> None:
        """Updates the status and logs update timestamp.

        Args:
            new_status: Target status string.
            progress: Progress percentage.
        """
        if new_status in self.LIFECYCLE_STATES:
            self.status = new_status
        self.progress = progress
        self.last_updated = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Converts task statistics to dictionary format."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "priority": self.priority,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "start_time": self.start_time,
            "completion_time": self.completion_time,
            "error_message": self.error_message,
            "cancelled": self.cancelled,
        }


class TaskQueue:
    """Manages scheduling queues and retrieves prioritised jobs."""

    def __init__(self):
        self._queue = queue.PriorityQueue()
        self._tasks: Dict[str, Task] = {}

    def submit(self, task: Task) -> str:
        """Enqueues a task.

        Args:
            task: Task instance.

        Returns:
            str: Unique Task ID.
        """
        self._tasks[task.task_id] = task
        self._queue.put((task.priority, task.created_at, task))
        return task.task_id

    def get_next(self) -> Optional[Task]:
        """Pulls the next scheduled task from queue.

        Returns:
            Optional[Task]: Decoded task or None.
        """
        try:
            _, _, task = self._queue.get_nowait()
            return task
        except queue.Empty:
            return None

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieves a task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        """Lists metadata of all registered tasks."""
        return [t.to_dict() for t in self._tasks.values()]
