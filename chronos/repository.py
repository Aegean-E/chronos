"""Data repository for sessions and tasks."""

from pathlib import Path
from typing import List, Optional

from chronos.models import Session, TaskItem
from chronos.storage import StorageEngine


class Repository:
    """Provides high-level queries and mutations for sessions and tasks."""

    def __init__(self, storage: StorageEngine):
        self.storage = storage

    def list_sessions(self) -> List[Session]:
        """Load all historical sessions."""
        data = self.storage.read_json_safe(self.storage.history_path, default=[])
        if not isinstance(data, list):
            return []
        return [Session.from_dict(item) for item in data if isinstance(item, dict)]

    def append_session(self, session: Session) -> None:
        """Append a completed or aborted session to history."""
        sessions = self.list_sessions()
        # Update existing by session_id if present, else append
        existing_idx = next((i for i, s in enumerate(sessions) if s.session_id == session.session_id), None)
        if existing_idx is not None:
            sessions[existing_idx] = session
        else:
            sessions.append(session)
        self.storage.write_json_atomic(self.storage.history_path, [s.to_dict() for s in sessions])

    def list_tasks(self) -> List[TaskItem]:
        """Load all tasks."""
        data = self.storage.read_json_safe(self.storage.tasks_path, default=[])
        if not isinstance(data, list):
            return []
        return [TaskItem.from_dict(item) for item in data if isinstance(item, dict)]

    def save_task(self, task: TaskItem) -> None:
        """Create or update a task item."""
        tasks = self.list_tasks()
        existing_idx = next((i for i, t in enumerate(tasks) if t.task_id == task.task_id), None)
        if existing_idx is not None:
            tasks[existing_idx] = task
        else:
            tasks.append(task)
        self.storage.write_json_atomic(self.storage.tasks_path, [t.to_dict() for t in tasks])

    def get_task(self, task_id: str) -> Optional[TaskItem]:
        """Find a task by its unique identifier."""
        return next((t for t in self.list_tasks() if t.task_id == task_id), None)
