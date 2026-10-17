# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.



### ADR-001: Architecture, Storage Schema, and Zero-Dependency CLI for Chronos
- **Date**: 2026-10-17
- **Status**: Accepted
- **Context**: Developers need a distraction-free, reliable tool to manage focus blocks, log interruptions, and track micro-milestones without depending on heavy third-party packages or remote clouds.
- **Decision**: Build Chronos as a modular Python package using only the Python standard library. Persist sessions and tasks locally in JSON format with atomic temp+fsync+replace writes and file locking. Expose an intuitive CLI with subcommands for start, pause, resume, finish, status, tasks, and stats.
- **Consequences**: Zero external package installation friction on Python 3.10+. File writes are resilient to power loss. Terminal output is clean and fast (<50ms execution).

