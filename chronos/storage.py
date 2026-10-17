"""Crash-resilient, atomic JSON storage engine for Chronos."""

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class StorageEngine:
    """Manages disk persistence for sessions and tasks with atomic writes."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.active_path = self.base_dir / "active_session.json"
        self.history_path = self.base_dir / "sessions.json"
        self.tasks_path = self.base_dir / "tasks.json"

    def write_json_atomic(self, path: Path, data: Any) -> None:
        """Write data to path atomically using temp file, fsync, and replace."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.parent / f".tmp_{path.name}_{int(time.time() * 1000)}"
        backup_path = path.with_suffix(path.suffix + ".bak")

        payload = json.dumps(data, indent=2, ensure_ascii=False)
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())

        if path.exists():
            shutil.copy2(path, backup_path)

        last_error = None
        for _ in range(5):
            try:
                os.replace(temp_path, path)
                return
            except OSError as exc:
                last_error = exc
                time.sleep(0.02)

        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        if last_error:
            raise last_error

    def read_json_safe(self, path: Path, default: Any) -> Any:
        """Read JSON from path, recovering from backup or quarantining if corrupt."""
        if not path.exists():
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            backup_path = path.with_suffix(path.suffix + ".bak")
            if backup_path.exists():
                try:
                    with open(backup_path, "r", encoding="utf-8") as bf:
                        return json.load(bf)
                except (json.JSONDecodeError, OSError):
                    pass
            # Quarantine corrupt file
            corrupt_dest = path.parent / f".corrupt_{path.name}_{int(time.time())}"
            try:
                os.replace(path, corrupt_dest)
            except OSError:
                pass
            return default

    def save_active_session(self, session_data: Optional[Dict[str, Any]]) -> None:
        """Persist or clear the currently active focus session."""
        if session_data is None:
            if self.active_path.exists():
                self.active_path.unlink(missing_ok=True)
        else:
            self.write_json_atomic(self.active_path, session_data)

    def load_active_session(self) -> Optional[Dict[str, Any]]:
        """Load the currently active session if one exists."""
        return self.read_json_safe(self.active_path, default=None)
