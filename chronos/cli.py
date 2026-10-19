"""Command-line interface for Chronos."""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from chronos import __version__
from chronos.analytics import compute_metrics, select_history
from chronos.models import SessionState, TaskItem, TaskStatus, now_iso, parse_iso, try_parse_iso
from chronos.orchestrator import SessionOrchestrator
from chronos.repository import Repository
from chronos.storage import StorageEngine


def _configure_output_encoding() -> None:
    """Keep emoji output from crashing when the terminal cannot encode it.

    Windows pipes and redirected files fall back to a legacy code page; writing
    UTF-8 with replacement characters beats a UnicodeEncodeError traceback.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # hygiene: allow best-effort re-encode; an odd stream must not abort the CLI
            pass


def _positive_int(value: str) -> int:
    """Argparse type: an integer of at least 1."""
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an integer, got '{value}'")
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got '{value}'")
    return parsed


def _non_negative_int(value: str) -> int:
    """Argparse type: an integer of at least 0."""
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an integer, got '{value}'")
    if parsed < 0:
        raise argparse.ArgumentTypeError(f"expected a non-negative integer, got '{value}'")
    return parsed


def get_default_data_dir() -> Path:
    """Return local .chronos or fallback directory."""
    local_dir = Path.cwd() / ".chronos"
    return local_dir


def format_progress_bar(elapsed_seconds: int, target_minutes: int, width: int = 24) -> str:
    """Render a terminal progress bar."""
    target_seconds = max(1, target_minutes * 60)
    fraction = min(1.0, elapsed_seconds / target_seconds)
    filled = int(fraction * width)
    bar = "█" * filled + "░" * (width - filled)
    percent = int(fraction * 100)
    return f"[{bar}] {percent}%"


def cmd_start(args: argparse.Namespace, orchestrator: SessionOrchestrator) -> int:
    try:
        session = orchestrator.start_session(
            title=args.title,
            target_minutes=args.duration,
            task_id=args.task,
            tag=args.tag,
        )
        print(f"⏱️  Started focus session '{session.title}' ({session.target_minutes}m, tag: {session.tag})")
        print(f"   ID: {session.session_id}")
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_pause(orchestrator: SessionOrchestrator) -> int:
    try:
        session = orchestrator.pause_session()
        mins = session.elapsed_seconds // 60
        secs = session.elapsed_seconds % 60
        print(f"⏸️  Paused session '{session.title}' (elapsed: {mins}m {secs}s)")
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_resume(orchestrator: SessionOrchestrator) -> int:
    try:
        session = orchestrator.resume_session()
        print(f"▶️  Resumed session '{session.title}'")
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_interrupt(args: argparse.Namespace, orchestrator: SessionOrchestrator) -> int:
    try:
        session = orchestrator.add_interruption(args.reason, duration_seconds=args.duration)
        print(f"⚡ Interruption logged: '{args.reason}' (total: {len(session.interruptions)})")
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_finish(args: argparse.Namespace, orchestrator: SessionOrchestrator) -> int:
    try:
        session = orchestrator.finish_session(notes=args.notes)
        mins = session.elapsed_seconds // 60
        secs = session.elapsed_seconds % 60
        print(f"🎉 Completed focus session '{session.title}'!")
        print(f"   Duration: {mins}m {secs}s | Interruptions: {len(session.interruptions)}")
        if session.notes:
            print(f"   Notes: {session.notes}")
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_abort(args: argparse.Namespace, orchestrator: SessionOrchestrator) -> int:
    try:
        session = orchestrator.abort_session(reason=args.reason)
        print(f"🛑 Aborted session '{session.title}' ({session.session_id})")
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_status(args: argparse.Namespace, orchestrator: SessionOrchestrator) -> int:
    session = orchestrator.get_active_session()
    if not session:
        if args.json:
            print(json.dumps({"active": False}))
        else:
            print("No active focus session. Start one with `chronos start <title>`.")
        return 0

    elapsed = session.elapsed_seconds
    if session.state == SessionState.ACTIVE and session.last_resumed_at:
        now_dt = datetime.now(timezone.utc)
        elapsed += max(0, int((now_dt - parse_iso(session.last_resumed_at)).total_seconds()))

    if args.json:
        data = session.to_dict()
        data["current_elapsed_seconds"] = elapsed
        print(json.dumps(data, indent=2))
        return 0

    state_icon = "🟢 ACTIVE" if session.state == SessionState.ACTIVE else "🟡 PAUSED"
    mins = elapsed // 60
    secs = elapsed % 60
    bar = format_progress_bar(elapsed, session.target_minutes)

    print("══════════════════════════════════════════════════════════")
    print(f"🕒 CHRONOS FOCUS SESSION: {session.title}")
    print("══════════════════════════════════════════════════════════")
    print(f"State:       {state_icon}")
    print(f"Progress:    {bar} ({mins}m {secs}s / {session.target_minutes}m)")
    print(f"Tag:         #{session.tag}")
    if session.task_id:
        print(f"Task ID:     {session.task_id}")
    print(f"Disruptions: {len(session.interruptions)} recorded")
    print("══════════════════════════════════════════════════════════")
    return 0


def cmd_stats(args: argparse.Namespace, repository: Repository) -> int:
    sessions = repository.list_sessions()
    metrics = compute_metrics(sessions, days_window=args.days)

    if args.json:
        print(json.dumps(metrics, indent=2))
        return 0

    print("══════════════════════════════════════════════════════════")
    print(f"📊 CHRONOS INSIGHTS (Last {args.days} Days)")
    print("══════════════════════════════════════════════════════════")
    print(f"🔥 Daily Streak:         {metrics['current_streak_days']} day(s)")
    print(f"⌛ Total Focus Time:     {metrics['total_focus_minutes']} minutes")
    print(f"🎯 Completed Sessions:   {metrics['completed_count']} / {metrics['total_sessions']}")
    print(f"⚡ Total Interruptions:  {metrics['total_interruptions']}")
    print(f"📈 Average Duration:     {metrics['average_session_minutes']} minutes")
    print(f"⏸️  Interruption Time:    {metrics['total_interruption_minutes']} minutes")
    if metrics["tags_minutes"]:
        print("🏷️  Tag Breakdown:")
        for tag, m in metrics["tags_minutes"].items():
            print(f"   • #{tag:<14} {m} min")
    print("══════════════════════════════════════════════════════════")
    return 0


def cmd_history(args: argparse.Namespace, repository: Repository) -> int:
    sessions = select_history(
        repository.list_sessions(),
        days_window=args.days,
        tag=args.tag,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps([session.to_dict() for session in sessions], indent=2))
        return 0

    if not sessions:
        print("No archived sessions found.")
        return 0

    print("══════════════════════════════════════════════════════════")
    print(f"📜 CHRONOS HISTORY ({len(sessions)} session(s))")
    print("══════════════════════════════════════════════════════════")
    for session in sessions:
        started = try_parse_iso(session.started_at)
        stamp = started.astimezone().strftime("%Y-%m-%d %H:%M") if started else "unknown time"
        icon = "✅" if session.state == SessionState.COMPLETED else "🛑"
        mins = session.elapsed_seconds // 60
        secs = session.elapsed_seconds % 60
        print(
            f"{icon} {stamp}  {session.title}  #{session.tag}  "
            f"{mins}m {secs}s  ⚡{len(session.interruptions)}"
        )
    print("══════════════════════════════════════════════════════════")
    return 0


def _unique_task_id(repository: Repository) -> str:
    """Generate a task id that cannot overwrite an existing task."""
    while True:
        candidate = f"task_{uuid.uuid4().hex[:6]}"
        if repository.get_task(candidate) is None:
            return candidate


def cmd_task(
    args: argparse.Namespace,
    repository: Repository,
    orchestrator: Optional[SessionOrchestrator] = None,
) -> int:
    if args.task_command == "add":
        title = args.title.strip()
        if not title:
            print("Error: Task title cannot be empty.", file=sys.stderr)
            return 1
        task_id = _unique_task_id(repository)
        task = TaskItem(
            task_id=task_id,
            title=title,
            estimated_minutes=args.estimate,
        )
        repository.save_task(task)
        print(f"✅ Added task '{task.title}' [{task.task_id}] (est: {task.estimated_minutes}m)")
        return 0

    if args.task_command == "list":
        tasks = repository.list_tasks()
        status_filter = getattr(args, "status", "all")
        if status_filter != "all":
            tasks = [t for t in tasks if t.status == status_filter]

        if getattr(args, "json", False):
            print(json.dumps([t.to_dict() for t in tasks], indent=2))
            return 0

        if not tasks:
            if status_filter != "all":
                print(f"No tasks found matching status '{status_filter}'.")
            else:
                print("No tasks found. Create one with `chronos task add <title>`.")
            return 0
        print("──────────────────────────────────────────────────────────")
        for t in tasks:
            status_symbol = "✔" if t.status == TaskStatus.DONE else ("▶" if t.status == TaskStatus.IN_PROGRESS else "○")
            spent_m = t.spent_seconds // 60
            print(f" {status_symbol} [{t.task_id}] {t.title:<30} ({spent_m}m / {t.estimated_minutes}m)")
        print("──────────────────────────────────────────────────────────")
        return 0

    if args.task_command == "done":
        task = repository.get_task(args.task_id)
        if not task:
            print(f"Error: Task '{args.task_id}' not found.", file=sys.stderr)
            return 1
        if task.status == TaskStatus.DONE:
            print(f"Task '{task.title}' is already done.")
            return 0
        task.status = TaskStatus.DONE
        task.completed_at = now_iso()
        repository.save_task(task)
        print(f"🎉 Marked task '{task.title}' as done!")
        return 0

    if args.task_command == "show":
        task = repository.get_task(args.task_id)
        if not task:
            print(f"Error: Task '{args.task_id}' not found.", file=sys.stderr)
            return 1
        all_sessions = repository.list_sessions()
        bound_sessions = [s for s in all_sessions if s.task_id == task.task_id]

        if getattr(args, "json", False):
            payload = {
                "task": task.to_dict(),
                "sessions": [s.to_dict() for s in bound_sessions],
            }
            print(json.dumps(payload, indent=2))
            return 0

        status_symbol = "✔" if task.status == TaskStatus.DONE else ("▶" if task.status == TaskStatus.IN_PROGRESS else "○")
        spent_m = task.spent_seconds // 60
        print("──────────────────────────────────────────────────────────")
        print(f"Task:        {task.title} [{task.task_id}]")
        print(f"Status:      {status_symbol} {task.status}")
        print(f"Estimate:    {task.estimated_minutes}m")
        print(f"Spent:       {spent_m}m ({task.spent_seconds}s)")
        print(f"Created:     {task.created_at}")
        if task.completed_at:
            print(f"Completed:   {task.completed_at}")
        if bound_sessions:
            print(f"Sessions ({len(bound_sessions)}):")
            for s in bound_sessions:
                dur_m = s.elapsed_seconds // 60
                note_str = f" - {s.notes}" if s.notes else ""
                print(f"  • {s.started_at} [{s.state}] {dur_m}m: {s.title}{note_str}")
        else:
            print("Sessions:    None recorded yet")
        print("──────────────────────────────────────────────────────────")
        return 0

    if args.task_command in ("remove", "delete", "rm"):
        task = repository.get_task(args.task_id)
        if not task:
            print(f"Error: Task '{args.task_id}' not found.", file=sys.stderr)
            return 1
        if orchestrator is not None:
            active = orchestrator.get_active_session()
            if active and active.task_id == task.task_id:
                print(
                    f"Error: Cannot remove task '{task.task_id}': an active session is currently bound to it.",
                    file=sys.stderr,
                )
                return 1
        repository.delete_task(task.task_id)
        print(f"🗑️  Removed task '{task.title}' [{task.task_id}]")
        return 0

    if args.task_command == "clear":
        cleared_count = repository.clear_completed_tasks()
        if cleared_count == 0:
            print("No completed tasks to clear.")
        else:
            print(f"🧹 Cleared {cleared_count} completed task(s).")
        return 0

    print("Usage: chronos task {add,list,done,show,remove,clear} ...", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chronos", description="Lightweight developer focus & session orchestrator")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--data-dir", type=Path, default=None, help="Directory to store Chronos session data")
    subparsers = parser.add_subparsers(dest="command")

    start_p = subparsers.add_parser("start", help="Start a new focus session")
    start_p.add_argument("title", help="Title or focus goal")
    start_p.add_argument("--duration", "-d", type=_positive_int, default=25, help="Target duration in minutes (default: 25)")
    start_p.add_argument("--tag", "-t", default="general", help="Tag category (e.g. coding, debug, review)")
    start_p.add_argument("--task", default=None, help="Optional task ID to bind this session to")

    subparsers.add_parser("pause", help="Pause the active session")
    subparsers.add_parser("resume", help="Resume a paused session")

    interrupt_p = subparsers.add_parser("interrupt", help="Log an interruption")
    interrupt_p.add_argument("reason", help="Cause of interruption (e.g. Slack, call, meeting)")
    interrupt_p.add_argument("--duration", type=_non_negative_int, default=0, help="Duration in seconds")

    finish_p = subparsers.add_parser("finish", help="Complete and archive active session")
    finish_p.add_argument("--notes", "-n", default="", help="Completion notes")

    abort_p = subparsers.add_parser("abort", help="Abort active session")
    abort_p.add_argument("--reason", "-r", default="", help="Reason for cancellation")

    status_p = subparsers.add_parser("status", help="Show active session status")
    status_p.add_argument("--json", action="store_true", help="Output JSON format")

    stats_p = subparsers.add_parser("stats", help="Display focus metrics and streak")
    stats_p.add_argument("--days", type=_positive_int, default=7, help="Lookback window in days (default: 7)")
    stats_p.add_argument("--json", action="store_true", help="Output JSON format")

    history_p = subparsers.add_parser("history", help="List archived focus sessions")
    history_p.add_argument("--days", type=_positive_int, default=None, help="Only sessions started within the last N days (default: all)")
    history_p.add_argument("--tag", default=None, help="Only sessions recorded with this tag")
    history_p.add_argument("--limit", type=_positive_int, default=20, help="Maximum number of sessions to show (default: 20)")
    history_p.add_argument("--json", action="store_true", help="Output JSON format")

    task_p = subparsers.add_parser("task", help="Task micro-milestone manager")
    task_subs = task_p.add_subparsers(dest="task_command")
    task_add = task_subs.add_parser("add", help="Add a task")
    task_add.add_argument("title", help="Task title")
    task_add.add_argument("--estimate", "-e", type=_positive_int, default=25, help="Estimated minutes")

    task_list = task_subs.add_parser("list", help="List all tasks")
    task_list.add_argument(
        "--status",
        "-s",
        choices=["all", "pending", "in_progress", "done"],
        default="all",
        help="Filter tasks by status (default: all)",
    )
    task_list.add_argument("--json", action="store_true", help="Output JSON format")

    task_done = task_subs.add_parser("done", help="Mark a task completed")
    task_done.add_argument("task_id", help="Task ID")

    task_show = task_subs.add_parser("show", help="Show task details and bound sessions")
    task_show.add_argument("task_id", help="Task ID")
    task_show.add_argument("--json", action="store_true", help="Output JSON format")

    task_remove = task_subs.add_parser("remove", aliases=["rm", "delete"], help="Remove a task")
    task_remove.add_argument("task_id", help="Task ID")

    task_subs.add_parser("clear", help="Clear all completed tasks")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    _configure_output_encoding()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    data_dir = args.data_dir or get_default_data_dir()
    storage = StorageEngine(data_dir)
    repository = Repository(storage)
    orchestrator = SessionOrchestrator(storage, repository)

    if args.command == "start":
        return cmd_start(args, orchestrator)
    if args.command == "pause":
        return cmd_pause(orchestrator)
    if args.command == "resume":
        return cmd_resume(orchestrator)
    if args.command == "interrupt":
        return cmd_interrupt(args, orchestrator)
    if args.command == "finish":
        return cmd_finish(args, orchestrator)
    if args.command == "abort":
        return cmd_abort(args, orchestrator)
    if args.command == "status":
        return cmd_status(args, orchestrator)
    if args.command == "stats":
        return cmd_stats(args, repository)
    if args.command == "history":
        return cmd_history(args, repository)
    if args.command == "task":
        return cmd_task(args, repository, orchestrator)

    return 0


if __name__ == "__main__":
    sys.exit(main())
