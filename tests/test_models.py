"""Unit tests for Chronos domain models."""

import unittest
from chronos.models import Interruption, Session, SessionState, TaskItem, TaskStatus


class TestModels(unittest.TestCase):
    def test_interruption_roundtrip(self):
        inter = Interruption(reason="Slack message", duration_seconds=120)
        data = inter.to_dict()
        restored = Interruption.from_dict(data)
        self.assertEqual(restored.reason, "Slack message")
        self.assertEqual(restored.duration_seconds, 120)

    def test_session_roundtrip(self):
        inter = Interruption(reason="Phone call", duration_seconds=60)
        session = Session(
            session_id="sess-001",
            title="Implement Core Engine",
            target_minutes=50,
            task_id="task-101",
            tag="coding",
            state=SessionState.ACTIVE,
            interruptions=[inter],
            notes="Focused deeply",
        )
        data = session.to_dict()
        restored = Session.from_dict(data)

        self.assertEqual(restored.session_id, "sess-001")
        self.assertEqual(restored.title, "Implement Core Engine")
        self.assertEqual(restored.target_minutes, 50)
        self.assertEqual(restored.task_id, "task-101")
        self.assertEqual(restored.tag, "coding")
        self.assertEqual(restored.state, SessionState.ACTIVE)
        self.assertEqual(len(restored.interruptions), 1)
        self.assertEqual(restored.interruptions[0].reason, "Phone call")
        self.assertEqual(restored.notes, "Focused deeply")

    def test_task_roundtrip(self):
        task = TaskItem(
            task_id="task-001",
            title="Design Schema",
            status=TaskStatus.IN_PROGRESS,
            estimated_minutes=30,
            spent_seconds=900,
        )
        data = task.to_dict()
        restored = TaskItem.from_dict(data)

        self.assertEqual(restored.task_id, "task-001")
        self.assertEqual(restored.title, "Design Schema")
        self.assertEqual(restored.status, TaskStatus.IN_PROGRESS)
        self.assertEqual(restored.estimated_minutes, 30)
        self.assertEqual(restored.spent_seconds, 900)


if __name__ == "__main__":
    unittest.main()
