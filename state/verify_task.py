#!/usr/bin/env python3
"""Default verification command for JARVIS OS tasks created from voice.

Why this exists
---------------
`create_task()` deliberately never accepts a `command` from voice/text input
— arbitrary shell from a conversational surface is a prompt-injection hole
(see the security note in core/jarvis_os_bridge.py). But orchestrator.py's
`run_verification()` treats an empty command as exit code -1, so every
voice-created task used to fail all its retries and land in 'blocked'
without anything actually being wrong. This script is the missing piece:
a *fixed*, non-injectable verification command that voice-created tasks get
by default (orchestrator.default_verification_command).

What it verifies
----------------
That the assigned agent actually wrote a non-empty artifact into the
Obsidian vault while this task was dispatched — a real file on disk, not
the agent's own claim of success. This keeps the Hallucination Loop
(specs/JARVIS_OS.md §7) honest: `claude -p` reporting "done!" proves
nothing here; a file with bytes in it does.

Paths written by the runtime itself are excluded, or every task would
trivially pass:
  - vault/wiki/mark_l_memory.md   — rewritten every 60s by the heartbeat's
                                     sync_memory_to_vault()
  - vault/outputs/task_summaries/ — written by write_task_summary() *after*
                                     a task reaches a terminal state
  - vault/.obsidian/              — Obsidian's own workspace state

Usage:
    python state/verify_task.py <task_id>

Exit codes:
    0  at least one qualifying non-empty vault artifact was written
    1  nothing was written (or the task/db/timestamp couldn't be read)
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "state" / "orchestrator.db"
VAULT_DIR = REPO_ROOT / "vault"

# Written by the runtime, not by an agent doing the task's actual work.
EXCLUDED_DIRS  = {
    VAULT_DIR / ".obsidian",
    VAULT_DIR / "outputs" / "task_summaries",
}
EXCLUDED_FILES = {
    VAULT_DIR / "wiki" / "mark_l_memory.md",
}

# Filesystem mtimes and SQLite's strftime() can disagree by a hair, and a
# task is dispatched a moment before its agent starts writing. A couple of
# seconds of slack avoids losing a genuine artifact on that boundary.
CLOCK_SKEW_SECONDS = 5.0


def dispatched_at_epoch(task_id: str) -> float | None:
    """UTC epoch seconds of the task's last status change — set by
    orchestrator.mark_dispatched() right before the agent runs."""
    if not DB_PATH.exists():
        print(f"verify_task: no database at {DB_PATH}", file=sys.stderr)
        return None

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT updated_at FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    except sqlite3.Error as exc:
        print(f"verify_task: could not read task {task_id}: {exc}", file=sys.stderr)
        return None
    finally:
        conn.close()

    if row is None or not row[0]:
        print(f"verify_task: no task row for id {task_id!r}", file=sys.stderr)
        return None

    raw = row[0].replace("Z", "+00:00")
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        print(f"verify_task: unparseable updated_at {row[0]!r}", file=sys.stderr)
        return None

    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.timestamp() - CLOCK_SKEW_SECONDS


def is_excluded(path: Path) -> bool:
    if path in EXCLUDED_FILES:
        return True
    return any(excluded in path.parents for excluded in EXCLUDED_DIRS)


def find_artifacts(since_epoch: float) -> list[Path]:
    """Non-empty vault files written at or after `since_epoch`."""
    if not VAULT_DIR.exists():
        return []

    found = []
    for path in VAULT_DIR.rglob("*"):
        if not path.is_file() or is_excluded(path):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime >= since_epoch and stat.st_size > 0:
            found.append(path)
    return found


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python state/verify_task.py <task_id>", file=sys.stderr)
        return 1

    task_id = argv[1]
    since = dispatched_at_epoch(task_id)
    if since is None:
        return 1

    artifacts = find_artifacts(since)
    if not artifacts:
        print(
            f"verify_task: task {task_id} produced no new vault artifact "
            f"(nothing non-empty written under {VAULT_DIR.name}/ since dispatch)",
            file=sys.stderr,
        )
        return 1

    print(f"verify_task: task {task_id} produced {len(artifacts)} vault artifact(s):")
    for path in artifacts:
        print(f"  {path.relative_to(REPO_ROOT)} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
