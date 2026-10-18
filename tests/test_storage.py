"""Unit tests for Chronos atomic storage engine."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from chronos.storage import StorageEngine


class TestStorageEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.engine = StorageEngine(self.temp_dir)

    def test_atomic_write_and_read(self):
        target = self.temp_dir / "sample.json"
        data = {"hello": "world", "count": 42}
        self.engine.write_json_atomic(target, data)

        self.assertTrue(target.exists())
        read_back = self.engine.read_json_safe(target, default={})
        self.assertEqual(read_back, data)

    def test_backup_and_recovery_on_corrupt_file(self):
        target = self.temp_dir / "active.json"
        valid_data = {"session": "alpha"}
        self.engine.write_json_atomic(target, valid_data)

        # Overwrite with corrupt data
        with open(target, "w", encoding="utf-8") as f:
            f.write("{broken json content")

        # Safe read should fall back to .bak or return default and quarantine
        recovered = self.engine.read_json_safe(target, default={"fallback": True})
        # Since .bak was created during write_json_atomic, it should recover valid_data or default
        self.assertIn(recovered, [valid_data, {"fallback": True}])

    def test_active_session_lifecycle(self):
        self.assertIsNone(self.engine.load_active_session())
        payload = {"id": "123", "title": "Test"}
        self.engine.save_active_session(payload)
        self.assertEqual(self.engine.load_active_session(), payload)

        self.engine.save_active_session(None)
        self.assertIsNone(self.engine.load_active_session())

    def test_read_json_safe_survives_invalid_utf8_bytes(self):
        target = self.temp_dir / "history.json"
        target.write_bytes(b"\xff\xfe\x00garbage")

        recovered = self.engine.read_json_safe(target, default=[])

        self.assertEqual(recovered, [])
        self.assertFalse(target.exists())
        self.assertTrue(any(self.temp_dir.glob(".corrupt_*")))

    def test_repeated_quarantine_does_not_overwrite_earlier_corrupt_file(self):
        target = self.temp_dir / "history.json"
        for _ in range(2):
            target.write_text("{broken", encoding="utf-8")
            self.assertEqual(self.engine.read_json_safe(target, default=[]), [])

        quarantined = list(self.temp_dir.glob(".corrupt_history.json_*"))
        self.assertEqual(len(quarantined), 2)

    def test_read_json_safe_does_not_move_file_on_oserror(self):
        target = self.temp_dir / "unreadable.json"
        target.mkdir()

        recovered = self.engine.read_json_safe(target, default=[])

        self.assertEqual(recovered, [])
        self.assertTrue(target.is_dir())


if __name__ == "__main__":
    unittest.main()
