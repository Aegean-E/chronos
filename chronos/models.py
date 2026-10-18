"""Domain models for Chronos focus sessions, tasks, and interruptions."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class SessionState:
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"


class TaskStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


def now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Interruption:
    """An interruption that occurred during a focus session."""
    reason: str
    started_at: str = field(default_factory=now_iso)
    duration_seconds: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Interruption":
        return cls(
            reason=data.get("reason", "Unknown"),
            started_at=data.get("started_at", now_iso()),
            duration_seconds=int(data.get("duration_seconds", 0)),
        )


@dataclass
class Session:
    """A developer focus or work session."""
    session_id: str
    title: str
    target_minutes: int
    task_id: Optional[str] = None
    tag: str = "general"
    state: str = SessionState.ACTIVE
    started_at: str = field(default_factory=now_iso)
    ended_at: Optional[str] = None
    elapsed_seconds: int = 0
    last_resumed_at: Optional[str] = None
    interruptions: List[Interruption] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["interruptions"] = [i.to_dict() for i in self.interruptions]
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        raw_interruptions = data.get("interruptions", [])
        interruptions = [
            Interruption.from_dict(item) if isinstance(item, dict) else item
            for item in raw_interruptions
        ]
        return cls(
            session_id=data.get("session_id", ""),
            title=data.get("title", "Focus Session"),
            target_minutes=int(data.get("target_minutes", 25)),
            task_id=data.get("task_id"),
            tag=data.get("tag", "general"),
            state=data.get("state", SessionState.ACTIVE),
            started_at=data.get("started_at", now_iso()),
            ended_at=data.get("ended_at"),
            elapsed_seconds=int(data.get("elapsed_seconds", 0)),
            last_resumed_at=data.get("last_resumed_at"),
            interruptions=interruptions,
            notes=data.get("notes", ""),
        )


@dataclass
class TaskItem:
    """A developer task or micro-milestone."""
    task_id: str
    title: str
    status: str = TaskStatus.PENDING
    estimated_minutes: int = 25
    spent_seconds: int = 0
    created_at: str = field(default_factory=now_iso)
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskItem":
        return cls(
            task_id=data.get("task_id", ""),
            title=data.get("title", ""),
            status=data.get("status", TaskStatus.PENDING),
            estimated_minutes=int(data.get("estimated_minutes", 25)),
            spent_seconds=int(data.get("spent_seconds", 0)),
            created_at=data.get("created_at", now_iso()),
            completed_at=data.get("completed_at"),
        )
