# chronos

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: git and Python 3.10+ (AIKit's gates); add this project's own.
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
├── .gitignore                <- transient AIKit state excluded
├── README.md
└── .aikit/                   <- this project's memory: record, ledger, decisions
```
