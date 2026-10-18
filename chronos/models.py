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


def parse_iso(value: Optional[str]) -> datetime:
    """Parse an ISO-8601 timestamp into a UTC-aware datetime.

    Naive input is read as UTC; missing or malformed input yields the current time.
    """
    try:
        parsed = datetime.fromisoformat(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_int(value: Any, default: int) -> int:
    """Coerce a stored value to int, falling back to default when malformed."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_text(value: Any, default: str = "") -> str:
    """Coerce a stored value to a non-empty string, falling back to default."""
    if isinstance(value, str):
        return value or default
    if value is None:
        return default
    return str(value)


def _as_optional_text(value: Any) -> Optional[str]:
    """Coerce a stored value to a string, or None when absent or empty."""
    if value is None:
        return None
    return str(value) or None


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
            reason=_as_text(data.get("reason"), "Unknown"),
            started_at=_as_text(data.get("started_at"), now_iso()),
            duration_seconds=_as_int(data.get("duration_seconds"), 0),
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
        raw_interruptions = data.get("interruptions")
        if not isinstance(raw_interruptions, list):
            raw_interruptions = []
        interruptions = [
            Interruption.from_dict(item) for item in raw_interruptions if isinstance(item, dict)
        ]
        return cls(
            session_id=_as_text(data.get("session_id")),
            title=_as_text(data.get("title"), "Focus Session"),
            target_minutes=_as_int(data.get("target_minutes"), 25),
            task_id=_as_optional_text(data.get("task_id")),
            tag=_as_text(data.get("tag"), "general"),
            state=_as_text(data.get("state"), SessionState.ACTIVE),
            started_at=_as_text(data.get("started_at"), now_iso()),
            ended_at=_as_optional_text(data.get("ended_at")),
            elapsed_seconds=_as_int(data.get("elapsed_seconds"), 0),
            last_resumed_at=_as_optional_text(data.get("last_resumed_at")),
            interruptions=interruptions,
            notes=_as_text(data.get("notes")),
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
            task_id=_as_text(data.get("task_id")),
            title=_as_text(data.get("title")),
            status=_as_text(data.get("status"), TaskStatus.PENDING),
            estimated_minutes=_as_int(data.get("estimated_minutes"), 25),
            spent_seconds=_as_int(data.get("spent_seconds"), 0),
            created_at=_as_text(data.get("created_at"), now_iso()),
            completed_at=_as_optional_text(data.get("completed_at")),
        )
