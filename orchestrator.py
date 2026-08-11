#!/usr/bin/env python3
"""JARVIS OS deterministic task orchestrator.

Connects to state/orchestrator.db, picks the next dependency-eligible
pending task, runs its verification command as a subprocess, and trusts
nothing but the exit code to decide whether the task is done.

See specs/JARVIS_OS.md §5 (task execution state) and §7 (the Hallucination
Loop) for the contract this implements.

Usage:
    python orchestrator.py                    # drain all eligible tasks once
    python orchestrator.py --watch             # keep polling for new work
    python orchestrator.py --init               # (re-)apply state/schema.sql first
    python orchestrator.py --db path/to.db -v   # custom db path, verbose logs
"""

from __future__ import annotations

import argparse
import logging
import re
import shlex
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = REPO_ROOT / "state" / "orchestrator.db"
SCHEMA_PATH = REPO_ROOT / "state" / "schema.sql"
DEFAULT_TIMEOUT_SECONDS = 300
NOW_EXPR = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"

# Supervisors safe to auto-dispatch from an unattended background cycle: none
# of these declare Bash in .claude/agents/<id>.md, so a headless call can't
# run shell commands on this machine with nobody watching. architect,
# orchestrator, performance, and synthesizer all have Bash and stay
# manual-only — invoked directly in a Claude Code session, never from here.
AUTO_DISPATCH_AGENTS = {"mentor", "brand", "interrogator", "scout", "radar"}

CLAUDE_CLI = "claude"
AGENT_TIMEOUT_SECONDS = 600

# Verification command handed to tasks created without an explicit one —
# principally everything from the `jarvis_os assign`/`draft_plan` voice
# actions, which never accept a `command` from conversational input (that
# would be a prompt-injection hole; see core/jarvis_os_bridge.create_task).
# Without this, run_verification() sees an empty command, returns -1, and
# every voice-created task burns its retries and lands in 'blocked' even
# when its agent did the work perfectly. The script itself is fixed and
# takes only a task id, so nothing user-spoken reaches a shell.
VERIFY_SCRIPT = "state/verify_task.py"


def default_verification_command(task_id: str) -> str:
    # shlex.quote, not a bare path: run_verification() parses with
    # shlex.split() in POSIX mode, which silently eats the backslashes in a
    # Windows interpreter path ("C:\...\python.exe" -> "C:...python.exe")
    # and would make every task fail as "command not found". Single-quoting
    # round-trips backslashes and spaces intact on every platform.
    return f"{shlex.quote(sys.executable)} {VERIFY_SCRIPT} {task_id}"
# Defense in depth: strips Bash from the headless call regardless of what
# the target subagent's own frontmatter declares, since permission scope is
# session-wide, not per-subagent.
_AGENT_ALLOWED_TOOLS = "Read,Write,Edit,Grep,Glob,WebSearch,WebFetch"

logger = logging.getLogger("orchestrator")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if schema_present(conn):
        _migrate(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    _migrate(conn)


def schema_present(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
    ).fetchone()
    return row is not None


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive, idempotent migrations for orchestrator.db files created
    before a schema change — runs on every connect() so a DB from before
    tasks.agent_prompt existed picks it up transparently."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    if "agent_prompt" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN agent_prompt TEXT DEFAULT ''")
        conn.commit()
    if "plan_id" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN plan_id TEXT DEFAULT NULL")
        conn.commit()

    agent_cols = {row["name"] for row in conn.execute("PRAGMA table_info(agents)").fetchall()}
    if "current_file_reference" not in agent_cols:
        conn.execute("ALTER TABLE agents ADD COLUMN current_file_reference TEXT DEFAULT ''")
        conn.commit()

    _migrate_awaiting_approval_status(conn)


def _migrate_awaiting_approval_status(conn: sqlite3.Connection) -> None:
    """SQLite can't ALTER a column's CHECK constraint in place, so a DB
    created before 'awaiting_approval' was a legal tasks.status value needs
    its tasks table rebuilt (the standard SQLite 12-step procedure) —
    otherwise every INSERT/UPDATE that tries to use the new status on an old
    DB fails the CHECK. No-op once the constraint already allows it.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'"
    ).fetchone()
    if row is None or "awaiting_approval" in row["sql"]:
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        BEGIN TRANSACTION;

        CREATE TABLE tasks_new (
            id                 TEXT PRIMARY KEY,
            title              TEXT NOT NULL,
            command             TEXT DEFAULT '',
            agent_prompt       TEXT DEFAULT '',
            assigned_agent_id  TEXT,
            plan_id            TEXT DEFAULT NULL,
            status             TEXT DEFAULT 'pending'
                               CHECK (status IN ('pending', 'in_progress', 'awaiting_approval', 'done', 'blocked')),
            retry_count        INTEGER DEFAULT 0,
            max_retries        INTEGER DEFAULT 3,
            created_at         TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            updated_at         TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            FOREIGN KEY (assigned_agent_id) REFERENCES agents(id)
        );

        INSERT INTO tasks_new (id, title, command, agent_prompt, assigned_agent_id,
                                plan_id, status, retry_count, max_retries, created_at, updated_at)
        SELECT id, title, command, agent_prompt, assigned_agent_id,
               plan_id, status, retry_count, max_retries, created_at, updated_at
        FROM tasks;

        DROP TABLE tasks;
        ALTER TABLE tasks_new RENAME TO tasks;

        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(assigned_agent_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_plan ON tasks(plan_id);

        COMMIT;
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def add_task(
    conn: sqlite3.Connection,
    task_id: str,
    title: str,
    assigned_agent_id: str,
    command: str = "",
    agent_prompt: str = "",
    max_retries: int = 3,
    status: str = "pending",
    plan_id: Optional[str] = None,
) -> None:
    """Insert a task row. Programmatic entry point for handing JARVIS OS a
    background task until the Command Center agents (orchestrator-decomposer)
    write tasks themselves (spec §10).

    status defaults to 'pending' (immediately eligible). Pass
    status='awaiting_approval' for a drafted task the Meta-Agent approval
    workflow should hold until a human calls approve_plan() — see
    create_plan() below and core/jarvis_os_bridge.py's create_plan().
    """
    conn.execute(
        "INSERT INTO tasks (id, title, command, assigned_agent_id, agent_prompt, max_retries, status, plan_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, title, command, assigned_agent_id, agent_prompt, max_retries, status, plan_id),
    )
    conn.commit()


def create_plan(
    conn: sqlite3.Connection,
    plan_title: str,
    assigned_agent_id: str,
    steps: list[str],
    agent_prompt: str = "",
    max_retries: int = 3,
) -> dict:
    """Draft a multi-step plan as a chain of tasks, all held in
    'awaiting_approval' until approve_plan() releases them — the Meta-Agent
    workflow: JARVIS can plan, but a human has to authorize it before the
    Hallucination Loop will ever dispatch a single step of it.

    Each step becomes its own task row sharing one plan_id, with step N+1
    depending on step N via task_dependencies — so even after approval, a
    multi-day plan still executes in order, one day unlocking the next only
    once it's verified 'done'.
    """
    plan_id = f"plan-{uuid.uuid4().hex[:8]}"
    task_ids = []
    for i, step_title in enumerate(steps):
        task_id = f"{plan_id}-step{i+1}"
        add_task(
            conn, task_id, f"{plan_title} — Day {i+1}: {step_title}", assigned_agent_id,
            command=default_verification_command(task_id),
            agent_prompt=agent_prompt, max_retries=max_retries,
            status="awaiting_approval", plan_id=plan_id,
        )
        if i > 0:
            conn.execute(
                "INSERT INTO task_dependencies (task_id, depends_on_task_id) VALUES (?, ?)",
                (task_id, task_ids[-1]),
            )
        task_ids.append(task_id)
    conn.commit()
    return {"plan_id": plan_id, "task_ids": task_ids, "title": plan_title, "agent": assigned_agent_id}


def approve_plan(conn: sqlite3.Connection, plan_id: str) -> int:
    """Move every 'awaiting_approval' task in a plan to 'pending', making it
    eligible for get_next_task() to pick up. Returns how many tasks were
    released. The only write path that moves a task OUT of
    'awaiting_approval' — nothing auto-approves a drafted plan."""
    cur = conn.execute(
        f"UPDATE tasks SET status = 'pending', updated_at = {NOW_EXPR} "
        f"WHERE plan_id = ? AND status = 'awaiting_approval'",
        (plan_id,),
    )
    conn.commit()
    return cur.rowcount


def get_awaiting_approval(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """All tasks currently held for approval, oldest first — used to answer
    'what's waiting on me?' and to find the most recently drafted plan when
    the user says 'approve the plan' without naming a plan_id."""
    return conn.execute(
        "SELECT * FROM tasks WHERE status = 'awaiting_approval' ORDER BY created_at ASC"
    ).fetchall()


def run_claude_agent(agent_id: str, prompt: str, timeout: int) -> tuple[int, str, str]:
    """Headless, non-interactive Claude Code call that hands real work to one
    supervisor subagent (specs/JARVIS_OS.md §10 — the trigger logic that
    lets the running app invoke .claude/agents/.claude/skills automatically).
    Only ever called for agent_id in AUTO_DISPATCH_AGENTS.

    This is the *work*, not the verification: apply_hallucination_loop still
    only trusts the task's own `command` exit code afterward. Whatever this
    agent claims is logged to execution_logs for audit but never by itself
    decides done/blocked — that would be exactly the "agent's own narrative"
    the Hallucination Loop exists to distrust (spec §7).
    """
    full_prompt = (
        f"Use the `{agent_id}` subagent (.claude/agents/{agent_id}.md) to "
        f"complete this task, then stop:\n\n{prompt}"
    )
    try:
        result = subprocess.run(
            [
                CLAUDE_CLI, "-p", full_prompt,
                "--output-format", "json",
                "--allowedTools", _AGENT_ALLOWED_TOOLS,
                "--max-turns", "15",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", "`claude` CLI not found on PATH — install Claude Code to enable agent auto-dispatch."
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        return -1, stdout, f"claude agent call timed out after {timeout}s"


def get_next_task(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    """Return the oldest pending task whose dependencies are all satisfied.

    A task is eligible when:
      - status = 'pending'
      - retry_count < max_retries (exhausted tasks are 'blocked', not retried here)
      - every row in task_dependencies for this task points at a task whose
        status = 'done' (a task with no dependency rows is always eligible
        on that criterion)
    """
    return conn.execute(
        """
        SELECT t.*
        FROM tasks t
        WHERE t.status = 'pending'
          AND t.retry_count < t.max_retries
          AND NOT EXISTS (
              SELECT 1
              FROM task_dependencies td
              JOIN tasks dep ON dep.id = td.depends_on_task_id
              WHERE td.task_id = t.id
                AND dep.status != 'done'
          )
        ORDER BY t.created_at ASC
        LIMIT 1
        """
    ).fetchone()


_REFERENCE_PATTERN = re.compile(
    r"https?://[^\s'\"]+"
    r"|[\w./\\-]+\.(?:py|md|json|sql|csv|yaml|yml|html|js|ts|tsx|jsx|db|txt)\b"
)


def _extract_reference(*texts: str) -> str:
    """Best-effort file path or URL mentioned in a task's agent_prompt/
    title/command — feeds agents.current_file_reference for the 3D UI's
    per-agent "what is it touching right now" display (see schema.sql).
    Heuristic text scan, not live syscall/file-handle tracing: tasks run as
    opaque subprocesses (run_verification) or headless `claude -p` calls
    (run_claude_agent) whose internal tool use isn't observable from here.

    Callers pass agent_prompt before command on purpose: since every
    voice-created task now carries default_verification_command(), the
    command string always mentions VERIFY_SCRIPT, and matching that would
    show the same harness path for every agent instead of the work it is
    actually doing. VERIFY_SCRIPT is skipped outright for the same reason.
    """
    for text in texts:
        if not text:
            continue
        for match in _REFERENCE_PATTERN.finditer(text):
            candidate = match.group(0)
            if candidate.replace("\\", "/").endswith(VERIFY_SCRIPT):
                continue
            return candidate
    return ""


def mark_dispatched(
    conn: sqlite3.Connection,
    task_id: str,
    agent_id: Optional[str],
    reference: str = "",
) -> None:
    conn.execute(
        f"UPDATE tasks SET status = 'in_progress', updated_at = {NOW_EXPR} WHERE id = ?",
        (task_id,),
    )
    if agent_id:
        conn.execute(
            "UPDATE agents SET status = 'busy', current_file_reference = ? WHERE id = ?",
            (reference, agent_id),
        )
    conn.commit()


def run_verification(command: str, timeout: int) -> tuple[int, str, str]:
    """Run a task's verification command. Only the exit code is ever trusted
    to mean success — stdout/stderr are logged for humans, never parsed to
    decide pass/fail (specs/JARVIS_OS.md §7).
    """
    if not command or not command.strip():
        return -1, "", "no verification command configured for this task"

    try:
        args = shlex.split(command)
    except ValueError as exc:
        return -1, "", f"could not parse command: {exc}"

    try:
        result = subprocess.run(
            args,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError as exc:
        return -1, "", f"command not found: {exc}"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        return -1, stdout, f"timed out after {timeout}s"


def log_execution(
    conn: sqlite3.Connection,
    task_id: str,
    command: str,
    exit_code: int,
    stdout: str,
    stderr: str,
) -> None:
    conn.execute(
        """
        INSERT INTO execution_logs (task_id, command_run, exit_code, stdout, stderr)
        VALUES (?, ?, ?, ?, ?)
        """,
        (task_id, command, exit_code, stdout, stderr),
    )
    conn.commit()


def apply_hallucination_loop(conn: sqlite3.Connection, task: sqlite3.Row, exit_code: int) -> str:
    """Update task/agent status from a verified exit code only — never from
    an agent's own narrative. Returns the resulting status: 'done' (exit
    code 0), 'pending' (queued for retry), or 'blocked' (max_retries
    exhausted; escalate to the next Daily Briefing instead of retrying
    forever).
    """
    task_id = task["id"]
    agent_id = task["assigned_agent_id"]

    if exit_code == 0:
        conn.execute(
            f"UPDATE tasks SET status = 'done', updated_at = {NOW_EXPR} WHERE id = ?",
            (task_id,),
        )
        result_status = "done"
    else:
        retry_count = task["retry_count"] + 1
        if retry_count >= task["max_retries"]:
            conn.execute(
                f"UPDATE tasks SET status = 'blocked', retry_count = ?, "
                f"updated_at = {NOW_EXPR} WHERE id = ?",
                (retry_count, task_id),
            )
            result_status = "blocked"
        else:
            conn.execute(
                f"UPDATE tasks SET status = 'pending', retry_count = ?, "
                f"updated_at = {NOW_EXPR} WHERE id = ?",
                (retry_count, task_id),
            )
            result_status = "pending"

    if agent_id:
        conn.execute(
            "UPDATE agents SET status = 'idle', current_file_reference = '' WHERE id = ?",
            (agent_id,),
        )
    conn.commit()
    return result_status


def process_next_task(conn: sqlite3.Connection, timeout: int) -> Optional[dict]:
    """Dispatch and verify a single task. Returns None if none was eligible,
    else a dict describing the outcome: {id, title, assigned_agent_id,
    status, exit_code} — status is 'done', 'blocked', or 'pending' (requeued
    for retry). Callers that just want a count (the CLI) or the full detail
    (the Mark-L bridge, for voice narration) both read off this same dict
    rather than the loop being implemented twice.
    """
    task = get_next_task(conn)
    if task is None:
        return None

    logger.info(
        "dispatching task %s (%s) to agent=%s",
        task["id"], task["title"], task["assigned_agent_id"],
    )
    agent_prompt = (task["agent_prompt"] or "") if "agent_prompt" in task.keys() else ""
    # agent_prompt first: it describes the real work, whereas `command` is
    # now almost always just the verifier harness (see _extract_reference).
    reference = _extract_reference(agent_prompt, task["title"], task["command"])
    mark_dispatched(conn, task["id"], task["assigned_agent_id"], reference)

    agent_id = task["assigned_agent_id"]
    if agent_prompt and agent_id in AUTO_DISPATCH_AGENTS:
        a_exit, a_out, a_err = run_claude_agent(agent_id, agent_prompt, AGENT_TIMEOUT_SECONDS)
        log_execution(conn, task["id"], f"claude -p --agent {agent_id}", a_exit, a_out, a_err)
        logger.info("agent %s call for task %s exited %s", agent_id, task["id"], a_exit)
        if a_exit != 0:
            # The agent invocation itself failed to even run — this attempt
            # is a failure regardless of what `command` would say, and we
            # don't want a stale verification pass from a PREVIOUS attempt
            # (e.g. an old output file still on disk) to paper over that.
            result_status = apply_hallucination_loop(conn, task, a_exit)
            if result_status == "blocked":
                logger.warning(
                    "task %s FAILED (agent exit_code=%s) -> blocked after %s/%s retries",
                    task["id"], a_exit, task["retry_count"] + 1, task["max_retries"],
                )
            return {
                "id": task["id"], "title": task["title"],
                "assigned_agent_id": agent_id, "status": result_status, "exit_code": a_exit,
            }
    elif agent_id not in AUTO_DISPATCH_AGENTS and agent_prompt:
        logger.warning(
            "task %s has an agent_prompt but assigned_agent_id=%s is not "
            "auto-dispatch-eligible — running verification only",
            task["id"], agent_id,
        )

    exit_code, stdout, stderr = run_verification(task["command"], timeout)
    log_execution(conn, task["id"], task["command"], exit_code, stdout, stderr)

    result_status = apply_hallucination_loop(conn, task, exit_code)

    if result_status == "done":
        logger.info("task %s PASSED (exit_code=0) -> done", task["id"])
    elif result_status == "blocked":
        logger.warning(
            "task %s FAILED (exit_code=%s) -> blocked after %s/%s retries; "
            "escalate to next Daily Briefing",
            task["id"], exit_code, task["retry_count"] + 1, task["max_retries"],
        )
    else:
        logger.warning(
            "task %s FAILED (exit_code=%s) -> requeued, retry %s/%s",
            task["id"], exit_code, task["retry_count"] + 1, task["max_retries"],
        )
    if stderr:
        logger.debug("stderr for %s: %s", task["id"], stderr.strip())

    return {
        "id": task["id"],
        "title": task["title"],
        "assigned_agent_id": task["assigned_agent_id"],
        "status": result_status,
        "exit_code": exit_code,
    }


def drain(conn: sqlite3.Connection, timeout: int) -> list[dict]:
    """Process every currently-eligible task until none remain, returning
    the outcome dict for each one processed (see process_next_task). A
    pending task that's permanently ineligible right now (unmet dependency,
    or a dependency that's itself blocked) is left alone rather than looped
    on.
    """
    results = []
    while True:
        outcome = process_next_task(conn, timeout)
        if outcome is None:
            break
        results.append(outcome)
    return results


def watch(conn: sqlite3.Connection, timeout: int, interval: int) -> None:
    logger.info("watching for eligible tasks every %ss (Ctrl+C to stop)", interval)
    try:
        while True:
            results = drain(conn, timeout)
            if results:
                logger.info("drained %d task(s)", len(results))
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("stopped")


def log_summary(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status").fetchall()
    counts = {row["status"]: row["n"] for row in rows}
    logger.info(
        "task summary: pending=%d in_progress=%d done=%d blocked=%d",
        counts.get("pending", 0),
        counts.get("in_progress", 0),
        counts.get("done", 0),
        counts.get("blocked", 0),
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="JARVIS OS deterministic task orchestrator")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="path to orchestrator.db")
    parser.add_argument("--init", action="store_true", help="(re-)apply state/schema.sql before running")
    parser.add_argument(
        "--watch", action="store_true",
        help="keep polling for newly-eligible tasks instead of exiting after one drain pass",
    )
    parser.add_argument("--interval", type=int, default=30, help="seconds between polls in --watch mode")
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS,
        help="per-task subprocess timeout in seconds",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    conn = connect(args.db)
    try:
        if args.init or not schema_present(conn):
            logger.info("initializing schema from %s", SCHEMA_PATH)
            ensure_schema(conn)

        if args.watch:
            watch(conn, args.timeout, args.interval)
        else:
            results = drain(conn, args.timeout)
            logger.info("drained %d task(s), no more eligible tasks", len(results))

        log_summary(conn)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
