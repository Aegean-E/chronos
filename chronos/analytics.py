"""Productivity metrics, streak tracking, and focus analytics."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from chronos.models import Session, SessionState, parse_iso


def compute_metrics(sessions: List[Session], days_window: int = 7) -> Dict[str, Any]:
    """Calculate focus metrics over the elapsed window; the streak spans all history given."""
    now = datetime.now(timezone.utc)
    window = timedelta(days=days_window)
    filtered = []
    for s in sessions:
        age = now - parse_iso(s.started_at)
        if timedelta(0) <= age <= window:
            filtered.append(s)

    total_seconds = sum(s.elapsed_seconds for s in filtered)
    completed_sessions = [s for s in filtered if s.state == SessionState.COMPLETED]
    aborted_sessions = [s for s in filtered if s.state == SessionState.ABORTED]

    total_interruptions = sum(len(s.interruptions) for s in filtered)

    # Tag distribution
    tags: Dict[str, int] = defaultdict(int)
    for s in filtered:
        tags[s.tag] += s.elapsed_seconds

    # Streak calculation: consecutive days ending today or yesterday, computed over every
    # completed session in the provided history so the count is never clipped by the window.
    active_dates = set()
    for s in sessions:
        if s.state != SessionState.COMPLETED:
            continue
        started = parse_iso(s.started_at)
        if started <= now:
            active_dates.add(started.strftime("%Y-%m-%d"))

    streak = 0
    today = now.strftime("%Y-%m-%d")
    check_day = now
    while True:
        day_str = check_day.strftime("%Y-%m-%d")
        if day_str in active_dates:
            streak += 1
            # Go back one day
            check_day = datetime.fromtimestamp(check_day.timestamp() - 86400, tz=timezone.utc)
        else:
            # If today has no completed session yet, check yesterday before ending streak
            if check_day.strftime("%Y-%m-%d") == today:
                check_day = datetime.fromtimestamp(check_day.timestamp() - 86400, tz=timezone.utc)
                if check_day.strftime("%Y-%m-%d") in active_dates:
                    streak += 1
                    check_day = datetime.fromtimestamp(check_day.timestamp() - 86400, tz=timezone.utc)
                    continue
            break

    avg_minutes = (total_seconds / 60.0 / len(filtered)) if filtered else 0.0

    return {
        "window_days": days_window,
        "total_sessions": len(filtered),
        "completed_count": len(completed_sessions),
        "aborted_count": len(aborted_sessions),
        "total_focus_minutes": round(total_seconds / 60.0, 1),
        "average_session_minutes": round(avg_minutes, 1),
        "total_interruptions": total_interruptions,
        "current_streak_days": streak,
        "tags_minutes": {tag: round(secs / 60.0, 1) for tag, secs in tags.items()},
    }
