"""Unit tests for Chronos repository."""

import shutil
import tempfile
import unittest
from pathlib import Path

from chronos.models import Session, TaskItem, TaskStatus
from chronos.repository import Repository
from chronos.storage import StorageEngine


class TestRepository(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.engine = StorageEngine(self.temp_dir)
        self.repo = Repository(self.engine)

    def test_session_append_and_list(self):
        self.assertEqual(self.repo.list_sessions(), [])
        sess1 = Session(session_id="s1", title="Deep Work", target_minutes=25)
        self.repo.append_session(sess1)

        sessions = self.repo.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].session_id, "s1")

        # Update existing session
        sess1.notes = "Completed early"
        self.repo.append_session(sess1)
        updated = self.repo.list_sessions()
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].notes, "Completed early")

    def test_task_save_and_query(self):
        self.assertEqual(self.repo.list_tasks(), [])
        task = TaskItem(task_id="t1", title="Write tests", status=TaskStatus.PENDING)
        self.repo.save_task(task)

        retrieved = self.repo.get_task("t1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Write tests")

        # Update status
        task.status = TaskStatus.DONE
        self.repo.save_task(task)
        self.assertEqual(self.repo.get_task("t1").status, TaskStatus.DONE)


if __name__ == "__main__":
    unittest.main()
