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

    def test_session_from_dict_coerces_malformed_numbers(self):
        restored = Session.from_dict({
            "session_id": "s1",
            "title": "t",
            "target_minutes": "abc",
            "elapsed_seconds": None,
        })

        self.assertEqual(restored.target_minutes, 25)
        self.assertEqual(restored.elapsed_seconds, 0)

    def test_session_from_dict_skips_malformed_interruptions(self):
        restored = Session.from_dict({
            "session_id": "s1",
            "title": "t",
            "interruptions": ["oops", None, {"reason": "real", "duration_seconds": "90"}],
        })

        self.assertEqual(len(restored.interruptions), 1)
        self.assertEqual(restored.interruptions[0].reason, "real")
        self.assertEqual(restored.interruptions[0].duration_seconds, 90)

    def test_session_from_dict_tolerates_non_list_interruptions(self):
        restored = Session.from_dict({
            "session_id": "s1",
            "title": "t",
            "interruptions": {"reason": "not a list"},
        })

        self.assertEqual(restored.interruptions, [])

    def test_interruption_and_task_from_dict_coerce_malformed_numbers(self):
        interruption = Interruption.from_dict({"reason": "x", "duration_seconds": None})
        task = TaskItem.from_dict({
            "task_id": "t1",
            "title": "x",
            "estimated_minutes": None,
            "spent_seconds": "oops",
        })

        self.assertEqual(interruption.duration_seconds, 0)
        self.assertEqual(task.estimated_minutes, 25)
        self.assertEqual(task.spent_seconds, 0)


if __name__ == "__main__":
    unittest.main()
