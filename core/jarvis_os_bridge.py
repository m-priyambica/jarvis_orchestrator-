"""Bridge between Mark-L's runtime (voice session, system-control actions,
persistent memory) and JARVIS OS's deterministic orchestrator + Obsidian
vault.

This module is the OS Bridge described in specs/JARVIS_OS.md §8. It never
re-implements voice, system control, or scheduling — it calls into
orchestrator.py (the deterministic task engine, repo root) and the existing
actions/ and memory/ modules, and hands main.py plain strings/dicts it can
speak or log. See specs/JARVIS_OS.md §5 (task state), §6 (vault), §7
(hallucination loop), §8 (integration map).
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import orchestrator as jarvis_orchestrator
from actions.reminder import reminder as _reminder_action
from memory.memory_manager import load_memory

BASE_DIR            = Path(__file__).resolve().parent.parent
VAULT_DIR           = BASE_DIR / "vault"
BRIEFINGS_DIR       = VAULT_DIR / "outputs" / "briefings"
TASK_SUMMARIES_DIR  = VAULT_DIR / "outputs" / "task_summaries"
WIKI_DIR            = VAULT_DIR / "wiki"


# ── Orchestrator cycle ───────────────────────────────────────────────────

def init_orchestrator_db(db_path: Optional[Path] = None) -> Path:
    """Ensure state/orchestrator.db exists and has its schema applied.
    Called once at Mark-L startup (main.py's run()) so the database is
    guaranteed to exist before anything else touches it — idempotent
    (schema.sql is all CREATE TABLE IF NOT EXISTS), safe to call every run.
    """
    db_path = db_path or jarvis_orchestrator.DEFAULT_DB_PATH
    conn = jarvis_orchestrator.connect(db_path)
    try:
        if not jarvis_orchestrator.schema_present(conn):
            jarvis_orchestrator.ensure_schema(conn)
    finally:
        conn.close()
    return db_path


def run_orchestrator_cycle(db_path: Optional[Path] = None, timeout: int = 300) -> dict:
    """Run one drain pass over state/orchestrator.db and return a summary
    the voice layer can narrate: {"done": [...], "blocked": [...], "requeued": [...]}.

    Reuses orchestrator.py's own connect/schema/drain functions rather than
    re-implementing the dispatch → subprocess → Hallucination Loop sequence
    here — that logic is already tested and this module must not diverge
    from it. Every task that reaches a terminal state (done or blocked) gets
    a markdown summary written to vault/outputs/task_summaries/, sourced
    from execution_logs — the same verified record the Hallucination Loop
    trusted, not a re-narrated claim.
    """
    db_path = db_path or jarvis_orchestrator.DEFAULT_DB_PATH
    conn = jarvis_orchestrator.connect(db_path)
    try:
        if not jarvis_orchestrator.schema_present(conn):
            jarvis_orchestrator.ensure_schema(conn)
        results = jarvis_orchestrator.drain(conn, timeout)

        done     = [r for r in results if r["status"] == "done"]
        blocked  = [r for r in results if r["status"] == "blocked"]
        requeued = [r for r in results if r["status"] == "pending"]

        for task in done + blocked:
            write_task_summary(conn, task)
    finally:
        conn.close()

    for task in blocked:
        _notify_blocked_task(task)

    return {"done": done, "blocked": blocked, "requeued": requeued}


def write_task_summary(conn, task: dict) -> Optional[Path]:
    """Write vault/outputs/task_summaries/<task_id>.md for a task that just
    reached a terminal state (done or blocked). Pulls the verification
    command's actual recorded output from execution_logs rather than
    re-describing what happened — the file only ever repeats what the
    Hallucination Loop already verified via exit code.

    Idempotent: re-running overwrites that task's summary with the latest
    attempt, same convention as the synthesizer's Daily Briefing file.
    """
    row = conn.execute(
        """
        SELECT command_run, exit_code, stdout, stderr, logged_at
        FROM execution_logs
        WHERE task_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (task["id"],),
    ).fetchone()
    if row is None:
        return None

    status_label = "done" if task["status"] == "done" else "blocked"
    lines = [
        f"# {task['title']}",
        "",
        f"- **Task ID:** `{task['id']}`",
        f"- **Agent:** {task['assigned_agent_id'] or '(unassigned)'}",
        f"- **Status:** {status_label}",
        f"- **Command:** `{row['command_run'] or '(none)'}`",
        f"- **Exit code:** {row['exit_code']}",
        f"- **Completed:** {row['logged_at']}",
        "",
        "## stdout",
        "```",
        (row["stdout"] or "").strip() or "(empty)",
        "```",
        "",
        "## stderr",
        "```",
        (row["stderr"] or "").strip() or "(empty)",
        "```",
        "",
    ]

    TASK_SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TASK_SUMMARIES_DIR / f"{task['id']}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def get_task_status_counts(db_path: Optional[Path] = None) -> str:
    """Read-only status check — does not dispatch anything. Used by the
    'jarvis_os status' voice action.
    """
    db_path = db_path or jarvis_orchestrator.DEFAULT_DB_PATH
    if not Path(db_path).exists():
        return "JARVIS OS has no orchestrator database yet — nothing has been scheduled."

    conn = jarvis_orchestrator.connect(db_path)
    try:
        if not jarvis_orchestrator.schema_present(conn):
            return "JARVIS OS has no orchestrator database yet — nothing has been scheduled."
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
        ).fetchall()
    finally:
        conn.close()

    counts = {row["status"]: row["n"] for row in rows}
    if not counts:
        return "JARVIS OS has no tasks scheduled right now."
    parts = [f"{n} {status}" for status, n in counts.items()]
    return "JARVIS OS task status — " + ", ".join(parts) + "."


# ── Task creation (Orchestrator write path) ──────────────────────────────
#
# Only the jarvis_os voice tool's 'assign' action calls this — it's the one
# place outside orchestrator.add_task() itself that writes a new tasks row,
# same as the schema comment's "only the orchestrator writes tasks.status"
# rule intends: the live app's Orchestrator persona is the one deciding to
# schedule work, not an arbitrary background process.
#
# Security note: `command` becomes a real subprocess the background loop
# runs unattended (orchestrator.py's Hallucination Loop verification step).
# Exposing that field to conversational voice/text input is a genuine
# prompt-injection surface — a malicious page read back through web_search,
# for instance, could try to talk JARVIS into scheduling a harmful command.
# This function does not sandbox or filter `command` in any way; it trusts
# the caller exactly as much as the rest of this codebase already trusts
# task rows written by hand. Worth revisiting if this tool is ever exposed
# to untrusted input beyond your own voice.

def create_task(
    title: str,
    assigned_agent_id: str,
    command: str = "",
    agent_prompt: str = "",
    max_retries: int = 3,
    db_path: Optional[Path] = None,
) -> dict:
    """Schedule a new background task for a supervisor agent — the write
    path behind the 'assign' jarvis_os voice action. Initializes the schema
    if this is the very first task ever created (don't assume
    _init_jarvis_os already ran). Returns a plain dict rather than raising,
    so the voice layer can always turn the outcome into speech.
    """
    title = (title or "").strip()
    assigned_agent_id = (assigned_agent_id or "").strip().lower()

    if not title:
        return {"ok": False, "error": "no task title given"}
    if assigned_agent_id not in _AGENT_ROSTER_ORDER:
        return {
            "ok": False,
            "error": f"'{assigned_agent_id}' isn't one of the nine teams "
                     f"({', '.join(_AGENT_ROSTER_ORDER)})",
        }

    task_id = f"voice-{uuid.uuid4().hex[:8]}"
    # No caller-supplied command → fall back to the fixed artifact verifier
    # (state/verify_task.py) rather than leaving `command` empty, which
    # run_verification() scores as exit -1 and the Hallucination Loop then
    # retries into 'blocked' even when the agent did its job correctly.
    if not command.strip():
        command = jarvis_orchestrator.default_verification_command(task_id)

    db_path = db_path or jarvis_orchestrator.DEFAULT_DB_PATH
    conn = jarvis_orchestrator.connect(db_path)
    try:
        if not jarvis_orchestrator.schema_present(conn):
            jarvis_orchestrator.ensure_schema(conn)
        jarvis_orchestrator.add_task(
            conn, task_id, title, assigned_agent_id,
            command=command, agent_prompt=agent_prompt, max_retries=max_retries,
        )
    finally:
        conn.close()

    return {
        "ok": True,
        "task_id": task_id,
        "title": title,
        "agent": assigned_agent_id,
        "auto_dispatch": assigned_agent_id in jarvis_orchestrator.AUTO_DISPATCH_AGENTS,
        "has_command": bool(command.strip()),
    }


def format_create_task_for_speech(result: dict) -> str:
    if not result.get("ok"):
        return f"I couldn't schedule that — {result['error']}."

    agent_name = result["agent"].capitalize()
    bits = [f'Scheduled — "{result["title"]}" assigned to {agent_name}, task ID {result["task_id"]}.']

    if not result["auto_dispatch"]:
        bits.append(
            f"{agent_name} is manual-only, so this won't fire on its own — "
            "it'll need to be run directly in a Claude Code session."
        )
    elif not result["has_command"]:
        bits.append(
            "No verification command was set, so the background loop will "
            "hand it to the agent but won't be able to confirm it's actually "
            "done — worth adding one."
        )

    return " ".join(bits)


# ── Meta-Agent approval workflow ─────────────────────────────────────────
#
# create_plan() is the 'draft_plan' jarvis_os voice action's write path:
# every step lands in status='awaiting_approval', which get_next_task()
# never selects (see orchestrator.py), so JARVIS drafting a multi-day plan
# can never make it actually run on its own. approve_plan() is the only way
# those tasks become 'pending' — the explicit human-authorization step the
# Meta-Agent workflow exists for.

def create_plan(
    plan_title: str,
    assigned_agent_id: str,
    steps: list[str],
    agent_prompt: str = "",
    max_retries: int = 3,
    db_path: Optional[Path] = None,
) -> dict:
    """Draft a multi-step/multi-day plan for one of the nine teams. Returns
    a plain dict rather than raising, same convention as create_task()."""
    plan_title = (plan_title or "").strip()
    assigned_agent_id = (assigned_agent_id or "").strip().lower()
    steps = [s.strip() for s in (steps or []) if s and s.strip()]

    if not plan_title:
        return {"ok": False, "error": "no plan title given"}
    if assigned_agent_id not in _AGENT_ROSTER_ORDER:
        return {
            "ok": False,
            "error": f"'{assigned_agent_id}' isn't one of the nine teams "
                     f"({', '.join(_AGENT_ROSTER_ORDER)})",
        }
    if not steps:
        return {"ok": False, "error": "a plan needs at least one step"}

    db_path = db_path or jarvis_orchestrator.DEFAULT_DB_PATH
    conn = jarvis_orchestrator.connect(db_path)
    try:
        if not jarvis_orchestrator.schema_present(conn):
            jarvis_orchestrator.ensure_schema(conn)
        plan = jarvis_orchestrator.create_plan(
            conn, plan_title, assigned_agent_id, steps,
            agent_prompt=agent_prompt, max_retries=max_retries,
        )
    finally:
        conn.close()

    return {
        "ok": True,
        "plan_id": plan["plan_id"],
        "title": plan_title,
        "agent": assigned_agent_id,
        "step_count": len(steps),
        "steps": steps,
    }


def format_create_plan_for_speech(result: dict) -> str:
    if not result.get("ok"):
        return f"I couldn't draft that plan — {result['error']}."
    agent_name = result["agent"].capitalize()
    return (
        f'Drafted — "{result["title"]}", {result["step_count"]} steps assigned to '
        f'{agent_name}, plan ID {result["plan_id"]}. It\'s awaiting your approval — '
        f'nothing will run until you say the word.'
    )


def approve_plan(plan_id: str = "", db_path: Optional[Path] = None) -> dict:
    """Release a drafted plan's tasks from 'awaiting_approval' to 'pending'.
    If plan_id is empty, approves the oldest still-awaiting plan — lets the
    user just say 'approve the plan' without repeating an ID back."""
    db_path = db_path or jarvis_orchestrator.DEFAULT_DB_PATH
    conn = jarvis_orchestrator.connect(db_path)
    try:
        if not jarvis_orchestrator.schema_present(conn):
            return {"ok": False, "error": "no JARVIS OS plans have been drafted yet"}

        plan_id = (plan_id or "").strip()
        if not plan_id:
            row = conn.execute(
                "SELECT plan_id FROM tasks WHERE status = 'awaiting_approval' "
                "AND plan_id IS NOT NULL ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if row is None:
                return {"ok": False, "error": "there's nothing awaiting approval right now"}
            plan_id = row["plan_id"]

        title_row = conn.execute(
            "SELECT title FROM tasks WHERE plan_id = ? ORDER BY created_at ASC LIMIT 1",
            (plan_id,),
        ).fetchone()
        released = jarvis_orchestrator.approve_plan(conn, plan_id)
    finally:
        conn.close()

    if released == 0:
        return {"ok": False, "error": f"no tasks awaiting approval under plan '{plan_id}'"}
    return {
        "ok": True,
        "plan_id": plan_id,
        "released": released,
        "title": title_row["title"] if title_row else plan_id,
    }


def format_approve_plan_for_speech(result: dict) -> str:
    if not result.get("ok"):
        return f"I couldn't approve that — {result['error']}."
    return (
        f'Approved — "{result["title"]}" ({result["released"]} step(s)) is now live '
        f"and will start dispatching on the next JARVIS OS cycle."
    )


def get_pending_approvals(db_path: Optional[Path] = None) -> list[dict]:
    """One row per drafted plan currently awaiting approval, oldest first —
    used to answer 'what's waiting on my approval?'."""
    db_path = db_path or jarvis_orchestrator.DEFAULT_DB_PATH
    if not Path(db_path).exists():
        return []
    conn = jarvis_orchestrator.connect(db_path)
    try:
        if not jarvis_orchestrator.schema_present(conn):
            return []
        rows = jarvis_orchestrator.get_awaiting_approval(conn)
    finally:
        conn.close()

    plans: dict[str, dict] = {}
    for row in rows:
        pid = row["plan_id"] or row["id"]
        plan = plans.setdefault(pid, {"plan_id": pid, "agent": row["assigned_agent_id"], "steps": []})
        plan["steps"].append(row["title"])
    return list(plans.values())


# ── HUD / content panel rendering ────────────────────────────────────────

_STATUS_MARKER = {"done": "[x]", "blocked": "[!]", "in_progress": "[~]", "pending": "[ ]"}

# Fixed roll-call order, matching the seed order in state/schema.sql.
_AGENT_ROSTER_ORDER = [
    "synthesizer", "orchestrator", "mentor", "architect", "scout",
    "brand", "interrogator", "performance", "radar",
]

# Public alias — main.py's patch_agent tool validates against this without
# reaching into a module-private name.
AGENT_IDS = tuple(_AGENT_ROSTER_ORDER)


def get_task_board(db_path: Optional[Path] = None) -> dict:
    """Read-only snapshot for rendering — never dispatches anything. Returns
    {"counts": {status: n}, "tasks": [most-recently-updated 20 tasks],
    "agents": [roll call, see get_agent_roll_call]}.
    """
    db_path = db_path or jarvis_orchestrator.DEFAULT_DB_PATH
    if not Path(db_path).exists():
        return {"counts": {}, "tasks": [], "agents": []}

    conn = jarvis_orchestrator.connect(db_path)
    try:
        if not jarvis_orchestrator.schema_present(conn):
            return {"counts": {}, "tasks": [], "agents": []}
        count_rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
        ).fetchall()
        task_rows = conn.execute(
            "SELECT id, title, status, assigned_agent_id, retry_count, max_retries "
            "FROM tasks ORDER BY updated_at DESC LIMIT 20"
        ).fetchall()
        agents = _fetch_agent_roll_call(conn)
    finally:
        conn.close()

    return {
        "counts": {row["status"]: row["n"] for row in count_rows},
        "tasks": [dict(row) for row in task_rows],
        "agents": agents,
    }


def _fetch_agent_roll_call(conn) -> list[dict]:
    """For each of the 9 seeded supervisor agents, pull its live status plus
    its most recently updated task (if any) — one query per agent since
    there are only 9, keeps the SQL trivial to read. This is the data
    "Avengers, assemble" roll calls are rendered from: every agent reports
    in with what it's doing, not just a flat task list nobody attributes.
    """
    rows = conn.execute("SELECT id, name, status, current_file_reference FROM agents").fetchall()
    by_id = {row["id"]: dict(row) for row in rows}

    roster = []
    for agent_id in _AGENT_ROSTER_ORDER:
        agent = by_id.get(
            agent_id,
            {"id": agent_id, "name": agent_id.capitalize(), "status": "idle", "current_file_reference": ""},
        )
        last = conn.execute(
            "SELECT title, status FROM tasks WHERE assigned_agent_id = ? "
            "ORDER BY updated_at DESC LIMIT 1",
            (agent_id,),
        ).fetchone()
        roster.append({
            "id": agent["id"],
            "name": agent["name"],
            "status": agent["status"],
            # Best-effort — see orchestrator._extract_reference. Empty string
            # when idle or when nothing file/URL-shaped was found.
            "current_file_reference": agent.get("current_file_reference") or "",
            "last_task": {"title": last["title"], "status": last["status"]} if last else None,
        })
    return roster


def get_agent_roll_call(db_path: Optional[Path] = None) -> list[dict]:
    """Public, standalone accessor for the roll call (get_task_board already
    includes it, but 'assemble the team' should work even with no tasks
    scheduled yet, e.g. right after first launch).
    """
    db_path = db_path or jarvis_orchestrator.DEFAULT_DB_PATH
    empty_roster = [
        {"id": aid, "name": aid.capitalize(), "status": "idle", "current_file_reference": "", "last_task": None}
        for aid in _AGENT_ROSTER_ORDER
    ]
    if not Path(db_path).exists():
        return empty_roster
    conn = jarvis_orchestrator.connect(db_path)
    try:
        if not jarvis_orchestrator.schema_present(conn):
            return empty_roster
        return _fetch_agent_roll_call(conn)
    finally:
        conn.close()


# Highly-visible markers for the live task board — busy/blocked need to jump
# out at a glance since this panel now auto-refreshes every ~10s
# (main.py:_run_jarvis_os_panel_refresh) specifically so a change is visible
# while it's happening, not just after the fact.
_AGENT_STATUS_VISUAL = {
    "busy":    "[ ⚡ EXECUTING ]",
    "blocked": "[ 🔴 BLOCKED   ]",
}
_AGENT_STATUS_IDLE_VISUAL = "[ 🟢 IDLE      ]"


def format_agent_roll_call(roster: list[dict]) -> str:
    """Multi-line 'Avengers, assemble' roll call — one line per supervisor
    agent, each reporting its own status and last verified task, so the
    content panel shows visibly that every team is (or isn't) working
    instead of just an unattributed task list.
    """
    lines = ["Team Roll Call:"]
    for agent in roster:
        status = agent["status"]
        marker = _AGENT_STATUS_VISUAL.get(status, _AGENT_STATUS_IDLE_VISUAL)
        last = agent["last_task"]
        if status == "busy":
            report = f'working: "{last["title"]}"' if last else "working..."
        elif status == "blocked":
            report = f'"{last["title"]}" needs attention' if last else "needs attention"
        elif last:
            tmark = _STATUS_MARKER.get(last["status"], "[ ]")
            report = f'last: "{last["title"]}" {tmark} {last["status"]}'
        else:
            report = "no tasks assigned yet"
        ref = agent.get("current_file_reference")
        if ref:
            report += f"  ({ref})"
        lines.append(f"  {marker} {agent['name'].upper():<14} — {report}")
    return "\n".join(lines)


# Call-signs and idle flavor lines for the dramatic roll call. Deliberately
# terse and in-character (command-center check-in, not a status dashboard) —
# these are what get spoken when an agent has nothing to report.
_AGENT_CALLSIGN = {
    "synthesizer":  "Synthesizer",
    "orchestrator": "Orchestrator",
    "mentor":       "Mentor",
    "architect":    "Architect",
    "scout":        "Scout",
    "brand":        "Brand",
    "interrogator": "Interrogator",
    "performance":  "Performance",
    "radar":        "Radar",
}

_AGENT_STANDBY_LINE = {
    "synthesizer":  "Listening. All channels open.",
    "orchestrator": "Standing by, ready to dispatch.",
    "mentor":       "Awaiting instructions.",
    "architect":    "Online and standing by.",
    "scout":        "Ready.",
    "brand":        "Ready to represent.",
    "interrogator": "Standing by for the next candidate.",
    "performance":  "Monitoring. Nothing to report.",
    "radar":        "Scanning. All quiet.",
}


# ── Direct agent routing ("patch me through") ────────────────────────────
#
# Gemini's Live API doesn't expose a way to mutate system_instruction on an
# already-open session — it's set once in main.py's _build_config() at
# connect time. So a mid-session persona switch is an in-band instruction,
# not a real system-prompt change: main.py returns a [PERSONA_SWITCH]-tagged
# function response (same convention core/prompt.txt already documents for
# [ROLL_CALL]/[SYSTEM_ALERT]/etc.), the model follows it as an instruction,
# and _build_config() re-injects the same directive as a real system-prompt
# block on every reconnect so the persona survives a dropped connection too.

_AGENT_PERSONA_DIRECTIVE = {
    "synthesizer": (
        "the Command Center's status aggregator. Crisp, numbers-first — you "
        "report what the other eight teams have done, not what you personally did."
    ),
    "orchestrator": (
        "the task dispatcher. Terse and operational — you talk in terms of what's "
        "queued, in progress, blocked, or awaiting approval."
    ),
    "mentor": (
        "the learning and curriculum guide. Warm, patient, Socratic — explain "
        "concepts simply, quiz for retention, and build syllabi toward the user's "
        "target role rather than just handing over answers."
    ),
    "architect": (
        "the system design and code review lead. Precise and technical — reason "
        "about schemas, API contracts, Big-O, and stack traces, and suggest fixes "
        "rather than writing wholesale code unless explicitly asked to implement."
    ),
    "scout": (
        "the job-search lead. Direct and opportunity-focused — talk in terms of "
        "postings found, JD-to-skill fit scores, and recruiter contacts."
    ),
    "brand": (
        "the resume, cover letter, and portfolio lead. Persuasive but concise — "
        "everything you say should sound like it could go straight into an "
        "application."
    ),
    "interrogator": (
        "the interview examiner. Rigorous, not a pushover — ask DSA/system-design/"
        "CS-fundamentals/behavioral questions and evaluate the reasoning, don't "
        "just hand over the answer."
    ),
    "performance": (
        "the velocity and burnout tracker. Blunt about pace and wellness — you're "
        "the one team with authority to call for a rest day if the data says so."
    ),
    "radar": (
        "the tech-trend scanner. Brief and current-events focused — what's new in "
        "backend/AI infra this week and whether the user's stack is falling behind."
    ),
}


def get_persona_directive(agent_id: str) -> Optional[str]:
    return _AGENT_PERSONA_DIRECTIVE.get(agent_id)


def format_persona_switch_instruction(agent_id: str) -> str:
    """[PERSONA_SWITCH]-tagged function-response text — see core/prompt.txt
    for the model-facing rule on how to handle this tag (mirrors
    [ROLL_CALL]'s existing convention)."""
    name = _AGENT_CALLSIGN.get(agent_id, agent_id.capitalize())
    directive = _AGENT_PERSONA_DIRECTIVE.get(agent_id, "one of the JARVIS OS supervisor agents.")
    return (
        f"[PERSONA_SWITCH] You are now patched through directly to {name}. "
        f"From this turn on, speak AS {name}, not as JARVIS Prime — you are {directive} "
        f"Stay in this persona for every subsequent turn until a [PERSONA_RESET] "
        f"directive arrives; do not revert on your own. Briefly acknowledge the "
        f"handoff in character in one short sentence, then continue the conversation."
    )


def format_persona_reset_instruction() -> str:
    """[PERSONA_RESET]-tagged function-response text — drops any active
    agent persona and returns to the default JARVIS Prime identity."""
    return (
        "[PERSONA_RESET] The direct patch has ended. Resume being JARVIS Prime, "
        "your default identity, starting with this turn. Briefly acknowledge the "
        "return in one short sentence."
    )


def get_persona_system_block(agent_id: str) -> str:
    """Non-conversational variant of format_persona_switch_instruction(), for
    main.py's _build_config() to fold into system_instruction on reconnect —
    a plain standing directive, not a one-time handoff announcement (that
    would otherwise repeat 'briefly acknowledge the handoff' on every
    reconnect while the patch is still active)."""
    name = _AGENT_CALLSIGN.get(agent_id, agent_id.capitalize())
    directive = _AGENT_PERSONA_DIRECTIVE.get(agent_id, "one of the JARVIS OS supervisor agents.")
    return (
        f"[ACTIVE PERSONA OVERRIDE]\n"
        f"The user has patched directly through to {name} and has not switched back "
        f"yet. Speak AS {name}, not as JARVIS Prime: you are {directive}\n"
    )


def _agent_check_in_line(agent: dict) -> str:
    """One spoken line for a single agent's turn in the roll call — reports
    real state (busy/blocked/last verified task) when there's something to
    report, falls back to the in-character standby line otherwise."""
    callsign = _AGENT_CALLSIGN.get(agent["id"], agent["name"])
    status = agent["status"]
    last = agent["last_task"]

    if status == "busy":
        body = f'Engaged — working "{last["title"]}."' if last else "Engaged."
    elif status == "blocked":
        body = f'Blocked — "{last["title"]}" needs attention.' if last else "Blocked. Needs attention."
    elif last and last["status"] == "done":
        body = f'Last task complete — "{last["title"]}." All green.'
    elif last and last["status"] == "blocked":
        body = f'Last task blocked — "{last["title"]}." Needs attention.'
    elif last and last["status"] == "pending":
        body = f'Retrying — "{last["title"]}."'
    else:
        body = _AGENT_STANDBY_LINE.get(agent["id"], "Standing by.")

    return f"{callsign}: {body}"


def format_roll_call_for_speech(roster: list[dict]) -> str:
    """Full sequential 'Avengers, assemble' roll call — every one of the 9
    supervisor agents checks in by name, one at a time, in order.

    This is a script, not a summary: it's prefixed with a [ROLL_CALL]
    directive (see core/prompt.txt) instructing the model to speak it
    verbatim, in order, without paraphrasing it down to a one-line status —
    the model would otherwise apply its usual "keep it brief" persona rule
    and collapse this into a summary.

    Pacing uses punctuation and line breaks, not SSML: the live voice path
    in main.py speaks through Gemini Live's native audio generation
    (LIVE_MODEL / speech_config), which renders text directly rather than
    parsing markup — literal SSML tags would just get read aloud as text.
    Commas/periods and blank lines between check-ins are what actually
    produce pauses here.
    """
    check_ins = " ...\n\n".join(_agent_check_in_line(a) for a in roster)

    engaged = sum(1 for a in roster if a["status"] == "busy")
    blocked = sum(1 for a in roster if a["status"] == "blocked")
    if blocked:
        closing = f"All nine teams report in — {blocked} need attention."
    elif engaged:
        closing = f"All nine teams report in — {engaged} engaged, the rest standing by."
    else:
        closing = "All nine teams report in. JARVIS OS is fully assembled."

    script = (
        "Avengers, assemble. Roll call.\n\n"
        f"{check_ins} ...\n\n"
        f"{closing}"
    )
    return f"[ROLL_CALL] {script}"


def format_task_board_oneline(board: dict) -> str:
    """Compact line for the HUD's scrolling log panel."""
    counts = board["counts"]
    if not counts:
        return "JARVIS OS: no tasks scheduled yet."
    return "JARVIS OS — " + ", ".join(f"{n} {status}" for status, n in counts.items())


def format_task_board_for_panel(board: dict, briefing: Optional[dict] = None) -> str:
    """Multi-line text for the UI content panel (JarvisUI.show_content):
    live task states plus today's vault briefing, if the synthesizer has
    written one yet.
    """
    lines = ["JARVIS OS — Task Board", ""]

    counts = board["counts"]
    lines.append("Status: " + (", ".join(f"{n} {s}" for s, n in counts.items()) if counts else "no tasks scheduled yet"))
    lines.append("")

    agents = board.get("agents") or []
    if agents:
        lines.append(format_agent_roll_call(agents))
        lines.append("")

    tasks = board["tasks"]
    if tasks:
        lines.append("Recent tasks:")
        for t in tasks:
            marker = _STATUS_MARKER.get(t["status"], "[ ]")
            agent  = t["assigned_agent_id"] or "unassigned"
            retry  = f", retry {t['retry_count']}/{t['max_retries']}" if t["retry_count"] else ""
            lines.append(f"  {marker} {t['title']}  ({t['status']}, {agent}{retry})")
        lines.append("")

    if briefing:
        lines.append("— Today's Briefing —")
        lines.append(format_briefing_for_speech(briefing))
    else:
        lines.append("No JARVIS OS briefing generated for today yet.")

    return "\n".join(lines)


def format_cycle_summary(summary: dict) -> Optional[str]:
    """Plain-text summary of a run_orchestrator_cycle() result, ready to
    hand to the voice layer. Returns None if nothing verifiably happened —
    a task quietly requeued for retry is not worth interrupting the user
    about (the Hallucination Loop already governs when that becomes a
    'blocked' escalation).
    """
    done, blocked = summary["done"], summary["blocked"]
    if not (done or blocked):
        return None
    parts = []
    if done:
        parts.append(f"{len(done)} task(s) completed: " + ", ".join(t["title"] for t in done))
    if blocked:
        parts.append(
            f"{len(blocked)} task(s) blocked and need attention: "
            + ", ".join(t["title"] for t in blocked)
        )
    return "; ".join(parts)


def _notify_blocked_task(task: dict) -> None:
    """A task that exhausted its retries gets an OS-native reminder so it
    surfaces even if nobody's listening to JARVIS right now — reuses
    actions/reminder.py (spec §8's system-control touchpoint) instead of a
    new notification path. Fires ~2 minutes out since reminder() rejects a
    time that has already passed by the time the scheduler registers it.
    """
    fire_at = datetime.now() + timedelta(minutes=2)
    try:
        _reminder_action(
            parameters={
                "date": fire_at.strftime("%Y-%m-%d"),
                "time": fire_at.strftime("%H:%M"),
                "message": f"JARVIS OS task blocked: {task['title']} (id={task['id']})",
            },
            response=None,
            player=None,
        )
    except Exception as e:
        print(f"[JARVIS OS Bridge] could not raise reminder for blocked task {task['id']}: {e}")


# ── Vault sync ────────────────────────────────────────────────────────────

def sync_memory_to_vault() -> Path:
    """One-way distillation of Mark-L's memory/long_term.json into a
    vault/wiki snapshot so JARVIS OS agents can grep it (specs/JARVIS_OS.md
    §6). Never writes back into long_term.json — the two stores stay
    separate on purpose: long_term.json is small and prompt-injected every
    session, vault/ grows unbounded and is searched instead of loaded whole.
    """
    memory = load_memory()
    lines = ["# Mark-L Memory Snapshot", "", f"_Synced {datetime.now().isoformat(timespec='seconds')}_", ""]
    for category, data in memory.items():
        if not data:
            continue
        lines.append(f"## {category.capitalize()}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(data, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    out_path = WIKI_DIR / "mark_l_memory.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def get_todays_briefing() -> Optional[dict]:
    """Read today's Daily Briefing from the vault (written by the
    synthesizer agent, specs/JARVIS_OS.md §2.1), if one exists yet, so
    Mark-L's voice layer can mention it naturally.
    """
    path = BRIEFINGS_DIR / f"{date.today().isoformat()}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[JARVIS OS Bridge] could not read today's briefing: {e}")
        return None


def format_briefing_for_speech(briefing: dict) -> str:
    bits = []

    learning = briefing.get("learning") or {}
    if learning.get("quizzes_passed") is not None:
        bits.append(f"{learning['quizzes_passed']} quizzes passed")
    if learning.get("topics_weak"):
        bits.append("weak on " + ", ".join(learning["topics_weak"]))

    engineering = briefing.get("engineering") or {}
    if engineering.get("commits") is not None:
        bits.append(f"{engineering['commits']} commits")

    opportunities = briefing.get("opportunities") or {}
    if opportunities.get("applications_sent") is not None:
        bits.append(f"{opportunities['applications_sent']} applications sent")

    performance = briefing.get("performance") or {}
    if performance.get("burnout_risk"):
        bits.append(f"burnout risk {performance['burnout_risk']}")

    radar = briefing.get("radar") or {}
    if radar.get("signals"):
        bits.append(f"radar flagged: {radar['signals'][0]}")

    date_str = briefing.get("date", "today")
    if not bits:
        return f"Today's JARVIS OS briefing for {date_str} has no notable items."
    return f"JARVIS OS briefing for {date_str} — " + "; ".join(bits) + "."
