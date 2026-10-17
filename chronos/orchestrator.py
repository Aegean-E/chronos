"""Session orchestrator managing session lifecycle, state transitions, and task binding."""

import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from chronos.models import Interruption, Session, SessionState, TaskStatus, now_iso
from chronos.repository import Repository
from chronos.storage import StorageEngine


class SessionOrchestrator:
    """Coordinates active session transitions and historical archiving."""

    def __init__(self, storage: StorageEngine, repository: Repository):
        self.storage = storage
        self.repository = repository

    def get_active_session(self) -> Optional[Session]:
        """Return the current in-flight session or None."""
        raw = self.storage.load_active_session()
        if not raw:
            return None
        return Session.from_dict(raw)

    def start_session(
        self,
        title: str,
        target_minutes: int = 25,
        task_id: Optional[str] = None,
        tag: str = "general",
    ) -> Session:
        """Start a new focus session. Raises RuntimeError if one is already active."""
        active = self.get_active_session()
        if active and active.state in (SessionState.ACTIVE, SessionState.PAUSED):
            raise RuntimeError(f"Session '{active.title}' ({active.session_id}) is currently active.")

        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        session = Session(
            session_id=session_id,
            title=title,
            target_minutes=target_minutes,
            task_id=task_id,
            tag=tag,
            state=SessionState.ACTIVE,
            started_at=now_iso(),
            last_resumed_at=now_iso(),
        )
        self.storage.save_active_session(session.to_dict())

        # If linked to a task, update its status to IN_PROGRESS
        if task_id:
            task = self.repository.get_task(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.IN_PROGRESS
                self.repository.save_task(task)

        return session

    def pause_session(self) -> Session:
        """Pause an active session, accumulating elapsed time."""
        session = self.get_active_session()
        if not session or session.state != SessionState.ACTIVE:
            raise RuntimeError("No active session to pause.")

        now_dt = datetime.now(timezone.utc)
        if session.last_resumed_at:
            resumed_dt = datetime.fromisoformat(session.last_resumed_at)
            delta = int((now_dt - resumed_dt).total_seconds())
            session.elapsed_seconds += max(0, delta)

        session.state = SessionState.PAUSED
        session.last_resumed_at = None
        self.storage.save_active_session(session.to_dict())
        return session

    def resume_session(self) -> Session:
        """Resume a paused session."""
        session = self.get_active_session()
        if not session or session.state != SessionState.PAUSED:
            raise RuntimeError("No paused session to resume.")

        session.state = SessionState.ACTIVE
        session.last_resumed_at = now_iso()
        self.storage.save_active_session(session.to_dict())
        return session

    def add_interruption(self, reason: str, duration_seconds: int = 0) -> Session:
        """Log an interruption on the active session."""
        session = self.get_active_session()
        if not session:
            raise RuntimeError("No active session to interrupt.")

        interruption = Interruption(reason=reason, duration_seconds=duration_seconds)
        session.interruptions.append(interruption)
        self.storage.save_active_session(session.to_dict())
        return session

    def finish_session(self, notes: str = "") -> Session:
        """Complete the active session and archive it into history."""
        session = self.get_active_session()
        if not session:
            raise RuntimeError("No active session to finish.")

        if session.state == SessionState.ACTIVE and session.last_resumed_at:
            now_dt = datetime.now(timezone.utc)
            resumed_dt = datetime.fromisoformat(session.last_resumed_at)
            delta = int((now_dt - resumed_dt).total_seconds())
            session.elapsed_seconds += max(0, delta)

        session.state = SessionState.COMPLETED
        session.ended_at = now_iso()
        if notes:
            session.notes = notes

        # Archive to repository and clear active slot
        self.repository.append_session(session)
        self.storage.save_active_session(None)

        # Update task spent time if linked
        if session.task_id:
            task = self.repository.get_task(session.task_id)
            if task:
                task.spent_seconds += session.elapsed_seconds
                self.repository.save_task(task)

        return session

    def abort_session(self, reason: str = "") -> Session:
        """Cancel and archive the current session as aborted."""
        session = self.get_active_session()
        if not session:
            raise RuntimeError("No active session to abort.")

        session.state = SessionState.ABORTED
        session.ended_at = now_iso()
        if reason:
            session.notes = f"Aborted: {reason}"

        self.repository.append_session(session)
        self.storage.save_active_session(None)
        return session
