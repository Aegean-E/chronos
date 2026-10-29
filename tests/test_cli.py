"""Integration tests for Chronos CLI commands."""

import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from chronos.cli import main


class TestCLIIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)

    def _session_row(self, session_id, title, started_at, tag="general",
                     state="completed", elapsed_seconds=600):
        return {
            "session_id": session_id,
            "title": title,
            "target_minutes": 25,
            "tag": tag,
            "state": state,
            "started_at": started_at,
            "elapsed_seconds": elapsed_seconds,
            "interruptions": [],
        }

    def _write_history(self, rows):
        (self.temp_dir / "sessions.json").write_text(json.dumps(rows), encoding="utf-8")

    def run_cli(self, *args):
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        cmd_args = ["--data-dir", str(self.temp_dir)] + list(args)
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exit_code = main(cmd_args)
        return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_every_command_holds_the_data_directory_lock(self):
        # ADR-007: the CLI lock covers the whole read-modify-write command, not just a write.
        with patch("chronos.cli.StorageEngine.locked", return_value=nullcontext()) as locked:
            exit_code, _, _ = self.run_cli("task", "list")

        self.assertEqual(exit_code, 0)
        locked.assert_called_once_with()

    def test_full_session_flow(self):
        # 1. Start task
        code, out, _ = self.run_cli("task", "add", "Build Integration Tests", "--estimate", "45")
        self.assertEqual(code, 0)
        self.assertIn("Added task", out)

        # 2. List tasks
        code, out, _ = self.run_cli("task", "list")
        self.assertEqual(code, 0)
        self.assertIn("Build Integration Tests", out)

        # 3. Start session
        code, out, _ = self.run_cli("start", "Coding Milestone", "--duration", "25", "--tag", "code")
        self.assertEqual(code, 0)
        self.assertIn("Started focus session", out)

        # 4. Status active
        code, out, _ = self.run_cli("status")
        self.assertEqual(code, 0)
        self.assertIn("ACTIVE", out)
        self.assertIn("#code", out)

        # 5. Status JSON
        code, out, _ = self.run_cli("status", "--json")
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["title"], "Coding Milestone")

        # 6. Pause & resume
        code, out, _ = self.run_cli("pause")
        self.assertEqual(code, 0)
        self.assertIn("Paused session", out)

        code, out, _ = self.run_cli("resume")
        self.assertEqual(code, 0)
        self.assertIn("Resumed session", out)

        # 7. Interrupt
        code, out, _ = self.run_cli("interrupt", "Slack DM", "--duration", "30")
        self.assertEqual(code, 0)
        self.assertIn("Interruption logged", out)

        # 8. Finish session
        code, out, _ = self.run_cli("finish", "--notes", "Shipped cleanly")
        self.assertEqual(code, 0)
        self.assertIn("Completed focus session", out)

        # 9. Verify stats
        code, out, _ = self.run_cli("stats")
        self.assertEqual(code, 0)
        self.assertIn("CHRONOS INSIGHTS", out)
        self.assertIn("Completed Sessions:   1 / 1", out)

        # 10. Verify stats JSON
        code, out, _ = self.run_cli("stats", "--json")
        self.assertEqual(code, 0)
        stats_json = json.loads(out)
        self.assertEqual(stats_json["completed_count"], 1)

    def test_abort_session(self):
        self.run_cli("start", "Doomed Session")
        code, out, _ = self.run_cli("abort", "--reason", "Emergency meeting")
        self.assertEqual(code, 0)
        self.assertIn("Aborted session", out)

        # Status should show no active session
        code, out, _ = self.run_cli("status")
        self.assertEqual(code, 0)
        self.assertIn("No active focus session", out)

    def test_history_lists_newest_first_and_filters_the_window(self):
        now = datetime.now(timezone.utc)
        self._write_history([
            self._session_row("s-old", "Old work", (now - timedelta(days=10)).isoformat(),
                              tag="coding"),
            self._session_row("s-new", "Recent work", (now - timedelta(hours=2)).isoformat(),
                              tag="review", elapsed_seconds=1200),
        ])

        code, out, _ = self.run_cli("history", "--days", "7")

        self.assertEqual(code, 0)
        self.assertIn("Recent work", out)
        self.assertNotIn("Old work", out)

        code, out, _ = self.run_cli("history", "--json")

        self.assertEqual(code, 0)
        rows = json.loads(out)
        self.assertEqual([row["session_id"] for row in rows], ["s-new", "s-old"])
        self.assertEqual(rows[0]["title"], "Recent work")

    def test_history_filters_by_tag_case_insensitively_and_limits(self):
        now = datetime.now(timezone.utc)
        self._write_history([
            self._session_row("s-code", "Code work", (now - timedelta(hours=1)).isoformat(),
                              tag="coding"),
            self._session_row("s-review", "Review work", (now - timedelta(hours=2)).isoformat(),
                              tag="review"),
        ])

        code, out, _ = self.run_cli("history", "--tag", "CODING", "--json")
        self.assertEqual(code, 0)
        self.assertEqual([row["session_id"] for row in json.loads(out)], ["s-code"])

        code, out, _ = self.run_cli("history", "--limit", "1", "--json")
        self.assertEqual(code, 0)
        self.assertEqual([row["session_id"] for row in json.loads(out)], ["s-code"])

    def test_history_reports_an_empty_history(self):
        code, out, _ = self.run_cli("history")
        self.assertEqual(code, 0)
        self.assertIn("No archived sessions found", out)

        code, out, _ = self.run_cli("history", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [])

    def test_commands_survive_legacy_encoded_stdout(self):
        buffer = io.BytesIO()
        wrapper = io.TextIOWrapper(buffer, encoding="cp1252")
        original = sys.stdout
        sys.stdout = wrapper
        try:
            code = main(["--data-dir", str(self.temp_dir), "task", "add", "Legacy console"])
            wrapper.flush()
        finally:
            sys.stdout = original

        self.assertEqual(code, 0)
        self.assertIn("Legacy console", buffer.getvalue().decode("utf-8"))

    def test_invalid_usage_arguments_report_exit_code_2(self):
        cases = [
            ["stats", "--days", "0"],
            ["stats", "--days", "-3"],
            ["history", "--days", "0"],
            ["history", "--limit", "0"],
            ["start", "title", "--duration", "0"],
            ["task", "add", "title", "--estimate", "0"],
            ["interrupt", "meeting", "--duration", "-1"],
        ]
        for case in cases:
            with self.subTest(case=case):
                stderr_buf = io.StringIO()
                with redirect_stderr(stderr_buf), self.assertRaises(SystemExit) as raised:
                    main(["--data-dir", str(self.temp_dir)] + case)
                self.assertEqual(raised.exception.code, 2)

    def test_start_rejects_unknown_task_binding(self):
        code, _, err = self.run_cli("start", "Typo session", "--task", "task_missing")
        self.assertEqual(code, 1)
        self.assertIn("not found", err)

        code, out, _ = self.run_cli("status")
        self.assertEqual(code, 0)
        self.assertIn("No active focus session", out)

    def test_task_add_rejects_empty_title(self):
        code, _, err = self.run_cli("task", "add", "   ")
        self.assertEqual(code, 1)
        self.assertIn("title", err)
        self.assertFalse((self.temp_dir / "tasks.json").exists())

    def test_interrupt_rejects_empty_reason(self):
        self.run_cli("start", "Interrupt validation")
        code, _, err = self.run_cli("interrupt", "   ")
        self.assertEqual(code, 1)
        self.assertIn("reason", err)

    def test_task_id_collision_does_not_overwrite_existing_task(self):
        tasks_path = self.temp_dir / "tasks.json"
        tasks_path.write_text(json.dumps([{
            "task_id": "task_aaaaaa",
            "title": "Original",
            "status": "pending",
            "estimated_minutes": 25,
            "spent_seconds": 0,
        }]), encoding="utf-8")

        class FakeUUID:
            def __init__(self, value):
                self.hex = value

        with patch("chronos.cli.uuid.uuid4", side_effect=[FakeUUID("aaaaaa"), FakeUUID("bbbbbb")]):
            code, out, _ = self.run_cli("task", "add", "Second task")

        self.assertEqual(code, 0)
        self.assertIn("task_bbbbbb", out)
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        self.assertEqual([t["task_id"] for t in tasks], ["task_aaaaaa", "task_bbbbbb"])

    def test_version_flag(self):
        stdout_buf = io.StringIO()
        with redirect_stdout(stdout_buf), self.assertRaises(SystemExit) as raised:
            main(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("0.1.0", stdout_buf.getvalue())

    def test_task_done_is_idempotent(self):
        code, out, _ = self.run_cli("task", "add", "Finish me once")
        self.assertEqual(code, 0)
        task_id = re.search(r"\[(task_[0-9a-f]+)\]", out).group(1)

        self.assertEqual(self.run_cli("task", "done", task_id)[0], 0)
        tasks_path = self.temp_dir / "tasks.json"
        first_completed_at = json.loads(tasks_path.read_text(encoding="utf-8"))[0]["completed_at"]

        code, out, _ = self.run_cli("task", "done", task_id)

        self.assertEqual(code, 0)
        self.assertIn("already", out)
        after_completed_at = json.loads(tasks_path.read_text(encoding="utf-8"))[0]["completed_at"]
        self.assertEqual(after_completed_at, first_completed_at)

    def test_task_remove_success_and_aliases(self):
        code, out, _ = self.run_cli("task", "add", "Task to remove")
        self.assertEqual(code, 0)
        task_id = re.search(r"\[(task_[0-9a-f]+)\]", out).group(1)

        # Remove with 'remove' command
        code, out, _ = self.run_cli("task", "remove", task_id)
        self.assertEqual(code, 0)
        self.assertIn(f"Removed task 'Task to remove' [{task_id}]", out)

        tasks_path = self.temp_dir / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        self.assertEqual(tasks, [])

        # Add another and remove with 'delete' alias
        code, out, _ = self.run_cli("task", "add", "Task to delete")
        self.assertEqual(code, 0)
        task_id2 = re.search(r"\[(task_[0-9a-f]+)\]", out).group(1)

        code, out, _ = self.run_cli("task", "delete", task_id2)
        self.assertEqual(code, 0)
        self.assertIn(f"Removed task 'Task to delete' [{task_id2}]", out)
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        self.assertEqual(tasks, [])

        # Add another and remove with 'rm' alias
        code, out, _ = self.run_cli("task", "add", "Task to rm")
        self.assertEqual(code, 0)
        task_id3 = re.search(r"\[(task_[0-9a-f]+)\]", out).group(1)

        code, out, _ = self.run_cli("task", "rm", task_id3)
        self.assertEqual(code, 0)
        self.assertIn(f"Removed task 'Task to rm' [{task_id3}]", out)
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        self.assertEqual(tasks, [])

    def test_task_clear(self):
        # 1. No completed tasks
        code, out, _ = self.run_cli("task", "clear")
        self.assertEqual(code, 0)
        self.assertIn("No completed tasks to clear.", out)

        # 2. Add pending task and two done tasks
        self.run_cli("task", "add", "Pending Task")
        _, out2, _ = self.run_cli("task", "add", "Done Task 1")
        t2_id = re.search(r"\[(task_[0-9a-f]+)\]", out2).group(1)
        _, out3, _ = self.run_cli("task", "add", "Done Task 2")
        t3_id = re.search(r"\[(task_[0-9a-f]+)\]", out3).group(1)

        self.run_cli("task", "done", t2_id)
        self.run_cli("task", "done", t3_id)

        # 3. Clear completed tasks
        code, out, _ = self.run_cli("task", "clear")
        self.assertEqual(code, 0)
        self.assertIn("Cleared 2 completed task(s).", out)

        # Check only pending task remains
        code, out, _ = self.run_cli("task", "list")
        self.assertIn("Pending Task", out)
        self.assertNotIn("Done Task 1", out)
        self.assertNotIn("Done Task 2", out)

    def test_task_remove_errors(self):
        # 1. Non-existent task
        code, _, err = self.run_cli("task", "remove", "task_nonexistent")
        self.assertEqual(code, 1)
        self.assertIn("not found", err)

        # 2. Cannot delete task bound to active session
        code, out, _ = self.run_cli("task", "add", "Bound Task")
        self.assertEqual(code, 0)
        task_id = re.search(r"\[(task_[0-9a-f]+)\]", out).group(1)

        code, _, _ = self.run_cli("start", "Active Session", "--task", task_id)
        self.assertEqual(code, 0)

        code, _, err = self.run_cli("task", "remove", task_id)
        self.assertEqual(code, 1)
        self.assertIn("active", err)

        # Clean up session
        self.run_cli("abort")

    def test_task_list_filtering_and_json(self):
        # Add 3 tasks
        self.run_cli("task", "add", "Pending Task")
        _, out2, _ = self.run_cli("task", "add", "In Progress Task")
        t2_id = re.search(r"\[(task_[0-9a-f]+)\]", out2).group(1)
        _, out3, _ = self.run_cli("task", "add", "Done Task")
        t3_id = re.search(r"\[(task_[0-9a-f]+)\]", out3).group(1)

        # Put t2 in progress
        self.run_cli("start", "Working t2", "--task", t2_id)
        self.run_cli("pause")

        # Put t3 done
        self.run_cli("task", "done", t3_id)

        # 1. Plain list without filter shows all 3
        code, out, _ = self.run_cli("task", "list")
        self.assertEqual(code, 0)
        self.assertIn("Pending Task", out)
        self.assertIn("In Progress Task", out)
        self.assertIn("Done Task", out)

        # 2. Filter by status: pending
        code, out, _ = self.run_cli("task", "list", "--status", "pending")
        self.assertEqual(code, 0)
        self.assertIn("Pending Task", out)
        self.assertNotIn("In Progress Task", out)
        self.assertNotIn("Done Task", out)

        # 3. Filter by status: in_progress
        code, out, _ = self.run_cli("task", "list", "--status", "in_progress")
        self.assertEqual(code, 0)
        self.assertIn("In Progress Task", out)
        self.assertNotIn("Pending Task", out)

        # 4. Filter by status: done
        code, out, _ = self.run_cli("task", "list", "--status", "done")
        self.assertEqual(code, 0)
        self.assertIn("Done Task", out)
        self.assertNotIn("Pending Task", out)

        # 5. List JSON output
        code, out, _ = self.run_cli("task", "list", "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(len(data), 3)

        # 6. List JSON output with status filter
        code, out, _ = self.run_cli("task", "list", "--status", "done", "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Done Task")

        # Clean up active session
        self.run_cli("abort")

    def test_task_show_text_and_json(self):
        code, out, _ = self.run_cli("task", "add", "Showcase Feature", "--estimate", "40")
        self.assertEqual(code, 0)
        task_id = re.search(r"\[(task_[0-9a-f]+)\]", out).group(1)

        # Run and finish a session bound to this task
        self.run_cli("start", "Coding feature", "--task", task_id)
        self.run_cli("finish", "--notes", "Part 1 completed")

        # 1. Text format
        code, out, _ = self.run_cli("task", "show", task_id)
        self.assertEqual(code, 0)
        self.assertIn("Showcase Feature", out)
        self.assertIn(task_id, out)
        self.assertIn("Coding feature", out)
        self.assertIn("Part 1 completed", out)

        # 2. JSON format
        code, out, _ = self.run_cli("task", "show", task_id, "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("task", payload)
        self.assertIn("sessions", payload)
        self.assertEqual(payload["task"]["task_id"], task_id)
        self.assertEqual(payload["task"]["title"], "Showcase Feature")
        self.assertEqual(len(payload["sessions"]), 1)
        self.assertEqual(payload["sessions"][0]["title"], "Coding feature")
        self.assertEqual(payload["sessions"][0]["notes"], "Part 1 completed")

        # 3. Non-existent task
        code, _, err = self.run_cli("task", "show", "task_unknown")
        self.assertEqual(code, 1)
        self.assertIn("not found", err)


if __name__ == "__main__":
    unittest.main()
