# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.



### ADR-001: Architecture, Storage Schema, and Zero-Dependency CLI for Chronos
- **Date**: 2026-10-17
- **Status**: Accepted
- **Context**: Developers need a distraction-free, reliable tool to manage focus blocks, log interruptions, and track micro-milestones without depending on heavy third-party packages or remote clouds.
- **Decision**: Build Chronos as a modular Python package using only the Python standard library. Persist sessions and tasks locally in JSON format with atomic temp+fsync+replace writes and file locking. Expose an intuitive CLI with subcommands for start, pause, resume, finish, status, tasks, and stats.
- **Consequences**: Zero external package installation friction on Python 3.10+. File writes are resilient to power loss. Terminal output is clean and fast (<50ms execution).


### ADR-002: Post-Review Correctness Fixes for Session Accounting, Stats, Storage and History Parsing
- **Date**: 2026-10-18
- **Status**: Accepted
- **Context**: An independent review of the shipped v1 found five defects: `abort` archived a session with `elapsed_seconds=0` for the whole active segment (only `finish` accumulated it), the stats window used floored days (counting a session 7d23h old in a 7-day view, and never rejecting future-dated rows), `datetime.fromisoformat` was trusted to return aware timestamps (naive input crashed `stats`), the atomic-write temp name derived from `time.time() * 1000` (two writers in one millisecond shared a scratch path), and a history row missing `session_id`/`task_id` raised `KeyError`, disabling every command until the file was fixed by hand.
- **Decision**: Accumulate the active segment in one shared helper used by pause, finish and abort; normalize every parsed timestamp to a UTC-aware value (naive input is read as UTC); filter the stats window by elapsed `timedelta`, ignoring future-dated rows; create temp files with `tempfile.mkstemp` and clean them in a `finally`; default missing identifiers to empty and skip id-less rows when listing sessions and tasks.
- **Consequences**: Aborted sessions keep their measured focus time; `stats` includes exactly the last N days; concurrent invocations cannot share a scratch path; a malformed row is skipped (and dropped on the next write) instead of disabling the CLI. The on-disk JSON schema is unchanged.


### ADR-003: Second Review — Crash-Proof Output, Tolerant Parsing, and Metric Corrections
- **Date**: 2026-10-18
- **Status**: Accepted
- **Context**: A second independent review reproduced four crash-class defects and four gaps: every command raised `UnicodeEncodeError` when stdout was a legacy-encoding pipe or redirected file (Windows cp1252/cp1254), `pause`/`finish`/`abort` raised `TypeError`/`ValueError` on a naive or malformed `last_resumed_at`, malformed history rows (non-integer fields, non-dict interruption entries) raised `ValueError`/`AttributeError` and disabled every command, invalid UTF-8 in a state file escaped the "safe" reader, the stats streak was clipped by `--days`, aborting a session never credited its bound task, `--days`/`--duration`/`--estimate` silently accepted non-positive values, and `task done` overwrote `completed_at` on repeat.
- **Decision**: Reconfigure stdout/stderr to UTF-8 with replacement at CLI entry; parse every stored timestamp through a shared `parse_iso` helper (naive read as UTC, malformed contributes zero); coerce stored numbers and text in `from_dict` and skip non-dict interruption entries; treat `ValueError` (malformed JSON or invalid encoding) as quarantinable content and never move a file that failed with a pure `OSError`; compute the streak over all provided history; credit aborted sessions to their bound tasks like finish; validate `--days`, `--duration` and `--estimate` as positive integers (usage exit code 2); make `task done` idempotent.
- **Consequences**: Malformed state, hand-edited rows, corrupt bytes and redirected output degrade gracefully instead of crashing. User-visible contract changes: non-positive duration/day/estimate arguments exit 2; the streak is no longer capped at the window; aborted focus time is credited to bound tasks; a repeated `task done` preserves the original completion timestamp. The on-disk JSON schema is unchanged. Known limitation (accepted): concurrent writers still follow last-writer-wins; no advisory lock is taken.


### ADR-004: Third Review — Idempotent Lifecycle, Bound-Task Validation, and Storage Durability
- **Date**: 2026-10-19
- **Status**: Accepted
- **Context**: A third adversarial review reproduced one double-counting defect and several gaps: a stale `completed` active record (surviving a crash between archiving and clearing the slot) could be finished again and credit its bound task twice; any valid-JSON non-object in `active_session.json` raised `AttributeError`; `start --task` silently accepted unknown IDs; negative interruption durations were stored; malformed history timestamps were excluded only by clock-ordering accident; 6-hex task IDs could collide and overwrite an unrelated task; quarantine names collided within one second; the directory entry was never flushed after a rename; and recorded interruption durations were never reported.
- **Decision**: Only `active`/`paused` records are treated as in flight, and the active record must be a non-empty object with a session ID; validate title, duration, task existence, interruption reason and duration at the orchestrator boundary; parse history timestamps with a strict `try_parse_iso` that skips malformed rows; generate task IDs until unused; use nanosecond quarantine names; fsync the parent directory after `os.replace` on POSIX; clamp stored negative durations/elapsed values; remove the active backup when the slot is cleared; report total interruption minutes; add `--version` and a non-negative parser for `interrupt --duration`.
- **Consequences**: Repeating `finish`/`abort` after a crash cannot double-credit task time; corrupted active-state shapes degrade to "no active session"; binding typos and invalid interruption input fail with a clear error (usage errors exit 2); task creation can never overwrite an existing task; quarantined evidence is preserved; malformed history rows no longer affect window or streak calculations. User-visible contract changes: unknown `--task` IDs and empty titles are rejected, and negative `--duration` values for `interrupt` exit 2. The on-disk JSON schema is unchanged. Known limitation (accepted): concurrent writers still follow last-writer-wins; no advisory lock is taken.


### ADR-005: Archived Session History Command
- **Date**: 2026-10-19
- **Status**: Accepted
- **Context**: `finish` and `abort` archive sessions into `sessions.json`, and `stats` aggregates them, but no command surfaced an individual session, so the archive was write-only for users: they could not review what they worked on, filter by tag, or consume the list programmatically.
- **Decision**: Add `chronos history` with `--days`, `--tag`, `--limit` (default 20) and `--json`, backed by a pure `select_history` helper in the analytics module that sorts newest first and reuses the metrics filter semantics: a row whose stored start timestamp is missing, malformed or in the future is skipped, and the window is elapsed time, not floored days.
- **Consequences**: The archive becomes readable without hand-editing JSON, with the same malformed-row behaviour as `stats`. No existing command changes and the on-disk schema is unchanged. Known limitation (accepted): rows with malformed timestamps are invisible to `history`, as they already were to `stats`.

