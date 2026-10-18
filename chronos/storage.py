"""Crash-resilient, atomic JSON storage engine for Chronos."""

import json
import os
import shutil
import tempfile
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Optional

_UNREADABLE = object()


class StorageEngine:
    """Manages disk persistence for sessions and tasks with atomic writes."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.active_path = self.base_dir / "active_session.json"
        self.history_path = self.base_dir / "sessions.json"
        self.tasks_path = self.base_dir / "tasks.json"

    def write_json_atomic(self, path: Path, data: Any) -> None:
        """Write data to path atomically using a unique temp file, fsync, and replace."""
        path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = path.with_suffix(path.suffix + ".bak")

        payload = json.dumps(data, indent=2, ensure_ascii=False)
        fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".tmp_{path.name}_")
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())

            if path.exists():
                shutil.copy2(path, backup_path)

            last_error = None
            for _ in range(5):
                try:
                    os.replace(temp_path, path)
                    self._fsync_directory(path.parent)
                    return
                except OSError as exc:
                    last_error = exc
                    time.sleep(0.02)
            if last_error:
                raise last_error
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        """Flush the directory entry on POSIX so a rename survives power loss.

        Windows cannot open a directory handle for fsync; os.replace is already
        durable enough there, so the call is a no-op instead of an error.
        """
        if os.name == "nt":
            return
        try:
            with closing(os.open(str(directory), os.O_RDONLY)) as fd:  # hygiene: allow directory fd is closed by closing()
                try:
                    os.fsync(fd)
                except OSError:
                    pass
        except OSError:
            pass

    def read_json_safe(self, path: Path, default: Any) -> Any:
        """Read JSON from path, recovering from backup or quarantining corrupt content."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return default
        except ValueError:
            # Malformed JSON or invalid text encoding: try the backup, then quarantine.
            recovered = self._read_backup(path)
            if recovered is not _UNREADABLE:
                return recovered
            self._quarantine(path)
            return default
        except OSError:
            # Unreadable for I/O reasons (lock, permissions); never move the file.
            recovered = self._read_backup(path)
            return default if recovered is _UNREADABLE else recovered

    def _read_backup(self, path: Path) -> Any:
        """Return parsed backup data, or _UNREADABLE when no readable backup exists."""
        backup_path = path.with_suffix(path.suffix + ".bak")
        if not backup_path.exists():
            return _UNREADABLE
        try:
            with open(backup_path, "r", encoding="utf-8") as bf:
                return json.load(bf)
        except (ValueError, OSError):
            return _UNREADABLE

    def _quarantine(self, path: Path) -> None:
        """Move an unreadable-content file aside so it cannot disable the CLI."""
        corrupt_dest = path.parent / f".corrupt_{path.name}_{time.time_ns()}"
        try:
            os.replace(path, corrupt_dest)
        except OSError:
            pass

    def save_active_session(self, session_data: Optional[Dict[str, Any]]) -> None:
        """Persist or clear the currently active focus session."""
        if session_data is None:
            if self.active_path.exists():
                self.active_path.unlink(missing_ok=True)
            # A finished session is archived; its stale backup must not be
            # resurrected as an active session if the slot is later corrupted.
            self.active_path.with_suffix(self.active_path.suffix + ".bak").unlink(missing_ok=True)
        else:
            self.write_json_atomic(self.active_path, session_data)

    def load_active_session(self) -> Optional[Dict[str, Any]]:
        """Load the currently active session if one exists."""
        return self.read_json_safe(self.active_path, default=None)
