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

    def test_list_sessions_skips_rows_missing_an_id(self):
        valid = Session(session_id="s1", title="Deep Work", target_minutes=25)
        self.engine.write_json_atomic(
            self.engine.history_path,
            [valid.to_dict(), {"title": "row without an id"}],
        )

        sessions = self.repo.list_sessions()

        self.assertEqual([s.session_id for s in sessions], ["s1"])

    def test_list_tasks_skips_rows_missing_an_id(self):
        valid = TaskItem(task_id="t1", title="Write tests")
        self.engine.write_json_atomic(
            self.engine.tasks_path,
            [{"title": "row without an id"}, valid.to_dict()],
        )

        tasks = self.repo.list_tasks()

        self.assertEqual([t.task_id for t in tasks], ["t1"])

    def test_list_sessions_tolerates_malformed_rows(self):
        self.engine.write_json_atomic(
            self.engine.history_path,
            [{"session_id": "s1", "title": "t", "target_minutes": "abc", "interruptions": ["oops"]}],
        )

        sessions = self.repo.list_sessions()

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].target_minutes, 25)
        self.assertEqual(sessions[0].interruptions, [])

        # Rewriting history must not crash on the tolerated row.
        self.repo.append_session(Session(session_id="s2", title="Clean", target_minutes=25))
        self.assertEqual(len(self.repo.list_sessions()), 2)


if __name__ == "__main__":
    unittest.main()
