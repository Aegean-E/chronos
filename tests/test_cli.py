"""Integration tests for Chronos CLI commands."""

import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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


if __name__ == "__main__":
    unittest.main()
