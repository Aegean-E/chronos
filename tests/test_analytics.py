"""Unit tests for Chronos metrics and analytics."""

import unittest
from datetime import datetime, timezone

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


if __name__ == "__main__":
    unittest.main()
