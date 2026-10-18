# chronos

Chronos is a lightweight, local-first developer focus and session orchestrator. It helps developers track deep-work sessions, manage micro-milestones, log interruptions, and generate productivity insights with zero external dependencies.

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: Python 3.10+ (standard library only; zero third-party packages required).
- **Canonical Regression Shield Gate**:
  ```bash
  python aikit.py check chronos
  ```

### 🛠️ AIKit Commands (run from the AIKit folder)
| Role | Command |
|---|---|
| Status, task and gates | `python aikit.py status chronos` |
| Phase 4: every gate | `python aikit.py check chronos` |
| Repair memory and map, then check | `python aikit.py fix chronos` |
| Resume an interrupted task | `python aikit.py resume chronos` |

## 📦 What's Inside

```text
chronos/
├── .aikit/                   <- this project's memory: record, ledger, decisions
├── .gitignore                <- transient AIKit state excluded
├── README.md
├── pyproject.toml            <- build and package configuration
├── chronos/                  <- core package source code
└── tests/                    <- unit and integration test suite
```

## 🚀 CLI Usage & Quick Start

Chronos requires only Python 3.10+ with standard library modules.

### 1. Starting and Managing Focus Sessions

```bash
# Start a 25-minute focus session
python -m chronos.cli start "Refactor storage layer" --duration 25 --tag coding

# Check live session progress and status
python -m chronos.cli status

# Pause during an interruption or meeting
python -m chronos.cli pause

# Resume focus
python -m chronos.cli resume

# Log an interruption with cause
python -m chronos.cli interrupt "Urgent Slack message" --duration 120

# Finish and log session notes
python -m chronos.cli finish --notes "Completed atomic tempfile writes"
```

### 2. Micro-Milestones & Tasks

```bash
# Add a micro-milestone
python -m chronos.cli task add "Implement test suite" --estimate 30

# List active and completed tasks
python -m chronos.cli task list

# Mark task complete
python -m chronos.cli task done <task_id>
```

### 3. Productivity Insights & Streaks

```bash
# View summary metrics for the past 7 days
python -m chronos.cli stats

# Export metrics as JSON for integration
python -m chronos.cli stats --json
```

## 🛡️ Architecture & Guarantees

- **Zero Undeclared Dependencies**: Built exclusively on Python 3 standard library (`argparse`, `json`, `pathlib`, `dataclasses`, `datetime`).
- **Crash Resilience**: State writes use atomic temp files with `fsync` and atomic `os.replace` to prevent corrupted state on sudden termination.
- **Fast Test Suite**: 100% test pass rate in <1 second with `python -m unittest discover`.


