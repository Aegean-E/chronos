"""Unit tests for Chronos session orchestrator."""

import shutil
import tempfile
import unittest
from pathlib import Path

from chronos.models import SessionState, TaskItem, TaskStatus
from chronos.orchestrator import SessionOrchestrator
from chronos.repository import Repository
from chronos.storage import StorageEngine


class TestSessionOrchestrator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.storage = StorageEngine(self.temp_dir)
        self.repo = Repository(self.storage)
        self.orchestrator = SessionOrchestrator(self.storage, self.repo)

    def test_start_and_finish_session(self):
        session = self.orchestrator.start_session("Refactor Storage", target_minutes=30)
        self.assertEqual(session.title, "Refactor Storage")
        self.assertEqual(session.state, SessionState.ACTIVE)

        active = self.orchestrator.get_active_session()
        self.assertIsNotNone(active)
        self.assertEqual(active.session_id, session.session_id)

        # Finishing session
        finished = self.orchestrator.finish_session(notes="Good progress")
        self.assertEqual(finished.state, SessionState.COMPLETED)
        self.assertIsNone(self.orchestrator.get_active_session())

        # Should be stored in repo history
        history = self.repo.list_sessions()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].session_id, session.session_id)

    def test_prevent_concurrent_active_sessions(self):
        self.orchestrator.start_session("First Session")
        with self.assertRaises(RuntimeError):
            self.orchestrator.start_session("Second Session")

    def test_pause_and_resume_session(self):
        session = self.orchestrator.start_session("Writing tests", target_minutes=20)
        paused = self.orchestrator.pause_session()
        self.assertEqual(paused.state, SessionState.PAUSED)

        resumed = self.orchestrator.resume_session()
        self.assertEqual(resumed.state, SessionState.ACTIVE)

    def test_interruption_logging(self):
        self.orchestrator.start_session("Deep Focus")
        updated = self.orchestrator.add_interruption("Urgent email", duration_seconds=180)
        self.assertEqual(len(updated.interruptions), 1)
        self.assertEqual(updated.interruptions[0].reason, "Urgent email")

    def test_task_binding_and_spent_time_accumulation(self):
        task = TaskItem(task_id="t-99", title="Build CLI", status=TaskStatus.PENDING)
        self.repo.save_task(task)

        # Starting session linked to task should update status to IN_PROGRESS
        sess = self.orchestrator.start_session("Build CLI session", task_id="t-99")
        updated_task = self.repo.get_task("t-99")
        self.assertEqual(updated_task.status, TaskStatus.IN_PROGRESS)

        # Finish session
        self.orchestrator.finish_session()
        updated_task_after = self.repo.get_task("t-99")
        self.assertGreaterEqual(updated_task_after.spent_seconds, 0)


if __name__ == "__main__":
    unittest.main()
