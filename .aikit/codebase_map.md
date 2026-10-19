# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `15`
- **Total Classes**: `15`
- **Total Top-Level Functions**: `26`
- **Total Class Methods**: `101`
- **Total Source Lines**: `1967`

---

## 📦 Modules & Exported Symbols

### [`chronos/__init__.py`](chronos/__init__.py)
> *Chronos: A lightweight developer focus and session orchestrator.*

**Size**: `3` lines (`94` bytes)

---

### [`chronos/analytics.py`](chronos/analytics.py)
> *Productivity metrics, streak tracking, and focus analytics.*

**Size**: `106` lines (`4297` bytes)

**Functions:**
- `def compute_metrics(sessions, days_window)` - *Calculate focus metrics over the elapsed window; the streak spans all history given.*
- `def select_history(sessions, days_window, tag, limit)` - *Return archived sessions newest first, filtered by elapsed window, tag and limit.*

---

### [`chronos/cli.py`](chronos/cli.py)
> *Command-line interface for Chronos.*

**Size**: `388` lines (`16889` bytes)

**Functions:**
- `def _configure_output_encoding()` - *Keep emoji output from crashing when the terminal cannot encode it.*
- `def _positive_int(value)` - *Argparse type: an integer of at least 1.*
- `def _non_negative_int(value)` - *Argparse type: an integer of at least 0.*
- `def get_default_data_dir()` - *Return local .chronos or fallback directory.*
- `def format_progress_bar(elapsed_seconds, target_minutes, width)` - *Render a terminal progress bar.*
- `def cmd_start(args, orchestrator)`
- `def cmd_pause(orchestrator)`
- `def cmd_resume(orchestrator)`
- `def cmd_interrupt(args, orchestrator)`
- `def cmd_finish(args, orchestrator)`
- `def cmd_abort(args, orchestrator)`
- `def cmd_status(args, orchestrator)`
- `def cmd_stats(args, repository)`
- `def cmd_history(args, repository)`
- `def _unique_task_id(repository)` - *Generate a task id that cannot overwrite an existing task.*
- `def cmd_task(args, repository)`
- `def build_parser()`
- `def main(argv)`

---

### [`chronos/models.py`](chronos/models.py)
> *Domain models for Chronos focus sessions, tasks, and interruptions.*

**Size**: `168` lines (`5659` bytes)

**Classes:**
- `class SessionState`
- `class TaskStatus`
- `class Interruption` - *An interruption that occurred during a focus session.*
  - Method `.to_dict()`
  - Method `.from_dict(data)`
- `class Session` - *A developer focus or work session.*
  - Method `.to_dict()`
  - Method `.from_dict(data)`
- `class TaskItem` - *A developer task or micro-milestone.*
  - Method `.to_dict()`
  - Method `.from_dict(data)`

**Functions:**
- `def now_iso()` - *Return the current UTC timestamp in ISO-8601 format.*
- `def try_parse_iso(value)` - *Parse an ISO-8601 timestamp into a UTC-aware datetime, or None when malformed.*
- `def parse_iso(value)` - *Parse an ISO-8601 timestamp into a UTC-aware datetime.*
- `def _as_int(value, default, minimum)` - *Coerce a stored value to int, falling back to default when malformed.*
- `def _as_text(value, default)` - *Coerce a stored value to a non-empty string, falling back to default.*
- `def _as_optional_text(value)` - *Coerce a stored value to a string, or None when absent or empty.*

---

### [`chronos/orchestrator.py`](chronos/orchestrator.py)
> *Session orchestrator managing session lifecycle, state transitions, and task binding.*

**Size**: `189` lines (`7353` bytes)

**Classes:**
- `class SessionOrchestrator` - *Coordinates active session transitions and historical archiving.*
  - Method `.__init__(storage, repository)`
  - Method `.get_active_session()` - *Return the current in-flight session or None.*
  - Method `._accumulate_active_segment(session)` - *Add the seconds since the last resume to the session's running total.*
  - Method `._credit_bound_task(session)` - *Add the session's measured focus time to its bound task, if any.*
  - Method `.start_session(title, target_minutes, task_id, tag)` - *Start a new focus session. Raises RuntimeError if one is already active.*
  - Method `.pause_session()` - *Pause an active session, accumulating elapsed time.*
  - Method `.resume_session()` - *Resume a paused session.*
  - Method `.add_interruption(reason, duration_seconds)` - *Log an interruption on the active session.*
  - Method `.finish_session(notes)` - *Complete the active session and archive it into history.*
  - Method `.abort_session(reason)` - *Cancel and archive the current session as aborted.*

---

### [`chronos/repository.py`](chronos/repository.py)
> *Data repository for sessions and tasks.*

**Size**: `53` lines (`2241` bytes)

**Classes:**
- `class Repository` - *Provides high-level queries and mutations for sessions and tasks.*
  - Method `.__init__(storage)`
  - Method `.list_sessions()` - *Load all historical sessions.*
  - Method `.append_session(session)` - *Append a completed or aborted session to history.*
  - Method `.list_tasks()` - *Load all tasks.*
  - Method `.save_task(task)` - *Create or update a task item.*
  - Method `.get_task(task_id)` - *Find a task by its unique identifier.*

---

### [`chronos/storage.py`](chronos/storage.py)
> *Crash-resilient, atomic JSON storage engine for Chronos.*

**Size**: `125` lines (`5146` bytes)

**Classes:**
- `class StorageEngine` - *Manages disk persistence for sessions and tasks with atomic writes.*
  - Method `.__init__(base_dir)`
  - Method `.write_json_atomic(path, data)` - *Write data to path atomically using a unique temp file, fsync, and replace.*
  - Method `._fsync_directory(directory)` - *Flush the directory entry on POSIX so a rename survives power loss.*
  - Method `.read_json_safe(path, default)` - *Read JSON from path, recovering from backup or quarantining corrupt content.*
  - Method `._read_backup(path)` - *Return parsed backup data, or _UNREADABLE when no readable backup exists.*
  - Method `._quarantine(path)` - *Move an unreadable-content file aside so it cannot disable the CLI.*
  - Method `.save_active_session(session_data)` - *Persist or clear the currently active focus session.*
  - Method `.load_active_session()` - *Load the currently active session if one exists.*

---

### [`tests/__init__.py`](tests/__init__.py)
> *Test suite for Chronos.*

**Size**: `1` lines (`30` bytes)

---

### [`tests/test_analytics.py`](tests/test_analytics.py)
> *Unit tests for Chronos metrics and analytics.*

**Size**: `172` lines (`6576` bytes)

**Classes:**
- `class TestAnalytics`
  - Method `.test_compute_metrics_empty()`
  - Method `.test_compute_metrics_with_sessions()`
  - Method `.test_window_uses_elapsed_time_not_floored_days()`
  - Method `.test_naive_timestamp_is_read_as_utc_not_crashing()`
  - Method `.test_future_dated_rows_are_ignored()`
  - Method `.test_streak_spans_more_days_than_the_window()`
  - Method `.test_streak_ignores_future_dated_sessions()`
  - Method `.test_malformed_timestamps_are_skipped_deterministically()`
  - Method `.test_history_selects_newest_first_within_window()`
  - Method `.test_history_filters_by_tag_case_insensitively()`
  - Method `.test_history_limit_keeps_the_newest_rows()`
  - Method `.test_history_skips_future_and_malformed_timestamps()`
  - Method `.test_history_empty()`
  - Method `._completed_session(session_id, started_at, elapsed_seconds, tag)`

---

### [`tests/test_cli.py`](tests/test_cli.py)
> *Integration tests for Chronos CLI commands.*

**Size**: `265` lines (`10032` bytes)

**Classes:**
- `class TestCLIIntegration`
  - Method `.setUp()`
  - Method `._session_row(session_id, title, started_at, tag, state, elapsed_seconds)`
  - Method `._write_history(rows)`
  - Method `.run_cli(*args)`
  - Method `.test_full_session_flow()`
  - Method `.test_abort_session()`
  - Method `.test_history_lists_newest_first_and_filters_the_window()`
  - Method `.test_history_filters_by_tag_case_insensitively_and_limits()`
  - Method `.test_history_reports_an_empty_history()`
  - Method `.test_commands_survive_legacy_encoded_stdout()`
  - Method `.test_invalid_usage_arguments_report_exit_code_2()`
  - Method `.test_start_rejects_unknown_task_binding()`
  - Method `.test_task_add_rejects_empty_title()`
  - Method `.test_interrupt_rejects_empty_reason()`
  - Method `.test_task_id_collision_does_not_overwrite_existing_task()`
  - Method `.test_version_flag()`
  - Method `.test_task_done_is_idempotent()`

---

### [`tests/test_init.py`](tests/test_init.py)
> *Smoke test for chronos package initialization.*

**Size**: `13` lines (`269` bytes)

**Classes:**
- `class TestChronosInit`
  - Method `.test_version_defined()`

---

### [`tests/test_models.py`](tests/test_models.py)
> *Unit tests for Chronos domain models.*

**Size**: `146` lines (`5163` bytes)

**Classes:**
- `class TestModels`
  - Method `.test_interruption_roundtrip()`
  - Method `.test_session_roundtrip()`
  - Method `.test_task_roundtrip()`
  - Method `.test_session_from_dict_coerces_malformed_numbers()`
  - Method `.test_session_from_dict_skips_malformed_interruptions()`
  - Method `.test_session_from_dict_tolerates_non_list_interruptions()`
  - Method `.test_interruption_and_task_from_dict_coerce_malformed_numbers()`
  - Method `.test_negative_stored_values_are_clamped()`
  - Method `.test_session_from_dict_leaves_missing_timestamp_empty()`
  - Method `.test_try_parse_iso_returns_none_for_malformed_and_normalizes_naive()`

---

### [`tests/test_orchestrator.py`](tests/test_orchestrator.py)
> *Unit tests for Chronos session orchestrator.*

**Size**: `168` lines (`7606` bytes)

**Classes:**
- `class TestSessionOrchestrator`
  - Method `.setUp()`
  - Method `.test_start_and_finish_session()`
  - Method `.test_prevent_concurrent_active_sessions()`
  - Method `.test_pause_and_resume_session()`
  - Method `.test_interruption_logging()`
  - Method `.test_task_binding_and_spent_time_accumulation()`
  - Method `.test_abort_accumulates_active_elapsed_time()`
  - Method `.test_naive_last_resumed_at_is_read_as_utc()`
  - Method `.test_garbage_last_resumed_at_does_not_crash_finish()`
  - Method `.test_abort_credits_bound_task_spent_time()`
  - Method `.test_stale_completed_active_state_is_ignored_and_not_recredited()`
  - Method `.test_non_object_active_state_is_treated_as_no_session()`
  - Method `.test_start_rejects_unknown_task_binding()`
  - Method `.test_start_rejects_empty_title_and_non_positive_duration()`
  - Method `.test_interruption_rejects_invalid_input()`
  - Method `._age_active_session(seconds, aware)` - *Backdate the active session's last resume so elapsed time is deterministic.*

---

### [`tests/test_repository.py`](tests/test_repository.py)
> *Unit tests for Chronos repository.*

**Size**: `90` lines (`3183` bytes)

**Classes:**
- `class TestRepository`
  - Method `.setUp()`
  - Method `.test_session_append_and_list()`
  - Method `.test_task_save_and_query()`
  - Method `.test_list_sessions_skips_rows_missing_an_id()`
  - Method `.test_list_tasks_skips_rows_missing_an_id()`
  - Method `.test_list_sessions_tolerates_malformed_rows()`

---

### [`tests/test_storage.py`](tests/test_storage.py)
> *Unit tests for Chronos atomic storage engine.*

**Size**: `80` lines (`2945` bytes)

**Classes:**
- `class TestStorageEngine`
  - Method `.setUp()`
  - Method `.test_atomic_write_and_read()`
  - Method `.test_backup_and_recovery_on_corrupt_file()`
  - Method `.test_active_session_lifecycle()`
  - Method `.test_read_json_safe_survives_invalid_utf8_bytes()`
  - Method `.test_repeated_quarantine_does_not_overwrite_earlier_corrupt_file()`
  - Method `.test_read_json_safe_does_not_move_file_on_oserror()`

---
