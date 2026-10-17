"""Command-line interface for Chronos."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from chronos.analytics import compute_metrics
from chronos.models import SessionState, TaskItem, TaskStatus
from chronos.orchestrator import SessionOrchestrator
from chronos.repository import Repository
from chronos.storage import StorageEngine


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
        try:
            now_dt = datetime.now(timezone.utc)
            last_resumed = datetime.fromisoformat(session.last_resumed_at)
            elapsed += max(0, int((now_dt - last_resumed).total_seconds()))
        except (ValueError, TypeError):
            pass

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
    if metrics["tags_minutes"]:
        print("🏷️  Tag Breakdown:")
        for tag, m in metrics["tags_minutes"].items():
            print(f"   • #{tag:<14} {m} min")
    print("══════════════════════════════════════════════════════════")
    return 0


def cmd_task(args: argparse.Namespace, repository: Repository) -> int:
    if args.task_command == "add":
        import uuid
        task_id = f"task_{uuid.uuid4().hex[:6]}"
        task = TaskItem(
            task_id=task_id,
            title=args.title,
            estimated_minutes=args.estimate,
        )
        repository.save_task(task)
        print(f"✅ Added task '{task.title}' [{task.task_id}] (est: {task.estimated_minutes}m)")
        return 0

    if args.task_command == "list":
        tasks = repository.list_tasks()
        if not tasks:
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
        task.status = TaskStatus.DONE
        task.completed_at = datetime.now(timezone.utc).isoformat()
        repository.save_task(task)
        print(f"🎉 Marked task '{task.title}' as done!")
        return 0

    print("Usage: chronos task {add,list,done} ...", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chronos", description="Lightweight developer focus & session orchestrator")
    parser.add_argument("--data-dir", type=Path, default=None, help="Directory to store Chronos session data")
    subparsers = parser.add_subparsers(dest="command")

    start_p = subparsers.add_parser("start", help="Start a new focus session")
    start_p.add_argument("title", help="Title or focus goal")
    start_p.add_argument("--duration", "-d", type=int, default=25, help="Target duration in minutes (default: 25)")
    start_p.add_argument("--tag", "-t", default="general", help="Tag category (e.g. coding, debug, review)")
    start_p.add_argument("--task", default=None, help="Optional task ID to bind this session to")

    subparsers.add_parser("pause", help="Pause the active session")
    subparsers.add_parser("resume", help="Resume a paused session")

    interrupt_p = subparsers.add_parser("interrupt", help="Log an interruption")
    interrupt_p.add_argument("reason", help="Cause of interruption (e.g. Slack, call, meeting)")
    interrupt_p.add_argument("--duration", type=int, default=0, help="Duration in seconds")

    finish_p = subparsers.add_parser("finish", help="Complete and archive active session")
    finish_p.add_argument("--notes", "-n", default="", help="Completion notes")

    abort_p = subparsers.add_parser("abort", help="Abort active session")
    abort_p.add_argument("--reason", "-r", default="", help="Reason for cancellation")

    status_p = subparsers.add_parser("status", help="Show active session status")
    status_p.add_argument("--json", action="store_true", help="Output JSON format")

    stats_p = subparsers.add_parser("stats", help="Display focus metrics and streak")
    stats_p.add_argument("--days", type=int, default=7, help="Lookback window in days (default: 7)")
    stats_p.add_argument("--json", action="store_true", help="Output JSON format")

    task_p = subparsers.add_parser("task", help="Task micro-milestone manager")
    task_subs = task_p.add_subparsers(dest="task_command")
    task_add = task_subs.add_parser("add", help="Add a task")
    task_add.add_argument("title", help="Task title")
    task_add.add_argument("--estimate", "-e", type=int, default=25, help="Estimated minutes")

    task_subs.add_parser("list", help="List all tasks")

    task_done = task_subs.add_parser("done", help="Mark a task completed")
    task_done.add_argument("task_id", help="Task ID")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
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
    if args.command == "task":
        return cmd_task(args, repository)

    return 0


if __name__ == "__main__":
    sys.exit(main())
