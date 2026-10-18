"""Session orchestrator managing session lifecycle, state transitions, and task binding."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from chronos.models import Interruption, Session, SessionState, TaskStatus, now_iso, parse_iso
from chronos.repository import Repository
from chronos.storage import StorageEngine


class SessionOrchestrator:
    """Coordinates active session transitions and historical archiving."""

    def __init__(self, storage: StorageEngine, repository: Repository):
        self.storage = storage
        self.repository = repository

    def get_active_session(self) -> Optional[Session]:
        """Return the current in-flight session or None.

        Only ACTIVE and PAUSED records are in flight. A stale COMPLETED/ABORTED
        record can survive a crash between archiving and clearing the active slot;
        ignoring it prevents a repeated finish/abort from crediting a task twice.
        """
        raw = self.storage.load_active_session()
        if not isinstance(raw, dict) or not raw:
            return None
        session = Session.from_dict(raw)
        if not session.session_id or session.state not in (SessionState.ACTIVE, SessionState.PAUSED):
            return None
        return session

    def _accumulate_active_segment(self, session: Session) -> None:
        """Add the seconds since the last resume to the session's running total.

        Naive timestamps are read as UTC and malformed ones contribute zero, so a
        hand-edited state file can never crash a lifecycle command.
        """
        if session.state != SessionState.ACTIVE or not session.last_resumed_at:
            return
        now_dt = datetime.now(timezone.utc)
        delta = int((now_dt - parse_iso(session.last_resumed_at)).total_seconds())
        session.elapsed_seconds += max(0, delta)

    def _credit_bound_task(self, session: Session) -> None:
        """Add the session's measured focus time to its bound task, if any."""
        if not session.task_id:
            return
        task = self.repository.get_task(session.task_id)
        if task:
            task.spent_seconds += session.elapsed_seconds
            self.repository.save_task(task)

    def start_session(
        self,
        title: str,
        target_minutes: int = 25,
        task_id: Optional[str] = None,
        tag: str = "general",
    ) -> Session:
        """Start a new focus session. Raises RuntimeError if one is already active."""
        title = title.strip() if isinstance(title, str) else ""
        if not title:
            raise RuntimeError("Session title cannot be empty.")
        try:
            target_minutes = int(target_minutes)
        except (TypeError, ValueError):
            raise RuntimeError("Session duration must be a positive integer.")
        if target_minutes < 1:
            raise RuntimeError("Session duration must be at least 1 minute.")
        tag = (tag.strip() if isinstance(tag, str) else "") or "general"

        bound_task = None
        if task_id:
            bound_task = self.repository.get_task(task_id)
            if bound_task is None:
                raise RuntimeError(f"Task '{task_id}' not found.")

        active = self.get_active_session()
        if active:
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
        if bound_task and bound_task.status == TaskStatus.PENDING:
            bound_task.status = TaskStatus.IN_PROGRESS
            self.repository.save_task(bound_task)

        return session

    def pause_session(self) -> Session:
        """Pause an active session, accumulating elapsed time."""
        session = self.get_active_session()
        if not session or session.state != SessionState.ACTIVE:
            raise RuntimeError("No active session to pause.")

        self._accumulate_active_segment(session)

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
        reason = reason.strip() if isinstance(reason, str) else ""
        if not reason:
            raise RuntimeError("Interruption reason cannot be empty.")
        try:
            duration_seconds = int(duration_seconds)
        except (TypeError, ValueError):
            raise RuntimeError("Interruption duration must be a non-negative integer.")
        if duration_seconds < 0:
            raise RuntimeError("Interruption duration cannot be negative.")

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

        self._accumulate_active_segment(session)

        session.state = SessionState.COMPLETED
        session.ended_at = now_iso()
        if notes:
            session.notes = notes

        # Archive to repository and clear active slot
        self.repository.append_session(session)
        self.storage.save_active_session(None)

        # Update task spent time if linked
        self._credit_bound_task(session)

        return session

    def abort_session(self, reason: str = "") -> Session:
        """Cancel and archive the current session as aborted."""
        session = self.get_active_session()
        if not session:
            raise RuntimeError("No active session to abort.")

        self._accumulate_active_segment(session)

        session.state = SessionState.ABORTED
        session.ended_at = now_iso()
        if reason:
            session.notes = f"Aborted: {reason}"

        self.repository.append_session(session)
        self.storage.save_active_session(None)

        # Aborted sessions keep their measured focus time, so credit it like finish.
        self._credit_bound_task(session)
        return session
