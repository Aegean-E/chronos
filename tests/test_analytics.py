"""Unit tests for Chronos metrics and analytics."""

import unittest
from datetime import datetime, timedelta, timezone

from chronos.analytics import compute_metrics
from chronos.models import Interruption, Session, SessionState, now_iso


class TestAnalytics(unittest.TestCase):
    def test_compute_metrics_empty(self):
        metrics = compute_metrics([])
        self.assertEqual(metrics["total_sessions"], 0)
        self.assertEqual(metrics["total_focus_minutes"], 0.0)
        self.assertEqual(metrics["current_streak_days"], 0)

    def test_compute_metrics_with_sessions(self):
        s1 = Session(
            session_id="s1",
            title="Session 1",
            target_minutes=30,
            tag="coding",
            state=SessionState.COMPLETED,
            elapsed_seconds=1800,
            interruptions=[Interruption(reason="call", duration_seconds=60)],
        )
        s2 = Session(
            session_id="s2",
            title="Session 2",
            target_minutes=20,
            tag="design",
            state=SessionState.COMPLETED,
            elapsed_seconds=1200,
            interruptions=[],
        )
        metrics = compute_metrics([s1, s2], days_window=7)
        self.assertEqual(metrics["total_sessions"], 2)
        self.assertEqual(metrics["completed_count"], 2)
        self.assertEqual(metrics["total_focus_minutes"], 50.0)
        self.assertEqual(metrics["total_interruptions"], 1)
        self.assertIn("coding", metrics["tags_minutes"])
        self.assertEqual(metrics["tags_minutes"]["coding"], 30.0)
        self.assertEqual(metrics["tags_minutes"]["design"], 20.0)
        self.assertGreaterEqual(metrics["current_streak_days"], 1)

    def test_window_uses_elapsed_time_not_floored_days(self):
        now = datetime.now(timezone.utc)
        old = self._completed_session("old", (now - timedelta(days=7, hours=23)).isoformat())
        fresh = self._completed_session("fresh", (now - timedelta(days=6, hours=23)).isoformat())

        metrics = compute_metrics([old, fresh], days_window=7)

        self.assertEqual(metrics["total_sessions"], 1)

    def test_naive_timestamp_is_read_as_utc_not_crashing(self):
        naive = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None).isoformat()

        metrics = compute_metrics([self._completed_session("naive", naive)], days_window=7)

        self.assertEqual(metrics["total_sessions"], 1)

    def test_future_dated_rows_are_ignored(self):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        metrics = compute_metrics([self._completed_session("future", future)], days_window=7)

        self.assertEqual(metrics["total_sessions"], 0)

    def _completed_session(self, session_id: str, started_at: str, elapsed_seconds: int = 600) -> Session:
        return Session(
            session_id=session_id,
            title=session_id,
            target_minutes=30,
            state=SessionState.COMPLETED,
            started_at=started_at,
            elapsed_seconds=elapsed_seconds,
        )


if __name__ == "__main__":
    unittest.main()
