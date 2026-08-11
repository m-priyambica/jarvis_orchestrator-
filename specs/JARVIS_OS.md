# JARVIS OS — Architecture Spec

Status: Draft v1 · Owner: Priyambica · Last updated: 2026-08-09

JARVIS OS is an autonomous, multi-agent layer built on top of **Mark-L** (this repo).
Mark-L already supplies the real-time voice/vision/system-control substrate
(`main.py`, `ui.py`, `core/`, `actions/`). JARVIS OS adds a command layer above it
that plans work, dispatches it to specialized sub-agents, tracks execution
deterministically, and remembers everything in a linked knowledge vault.

This document is the source of truth for that layer. The actual agent/skill
definitions Claude Code loads live in [`.claude/agents/`](../.claude/agents) and
[`.claude/skills/`](../.claude/skills); this spec explains *why* they're shaped
the way they are and how they connect to the rest of the repo.

---

## 1. Layered Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Command Center                                                  │
│  ┌────────────────┐        ┌──────────────────────┐              │
│  │  Synthesizer    │──────▶│  Main Orchestrator     │             │
│  │  (aggregator)   │  brief│  (planner/dispatcher)  │             │
│  └────────────────┘        └──────────────────────┘              │
│         ▲  reads logs               │ dispatches                 │
└─────────┼──────────────────────────┼─────────────────────────────┘
          │                          ▼
┌─────────┴──────────────────────────────────────────────────────┐
│  Domain Supervisors (5)         │  Support Supervisors (2)       │
│  Mentor · Architect · Scout ·   │  Performance · Radar           │
│  Brand · Interrogator           │                                │
└─────────┬──────────────────────┴────────────────┬───────────────┘
          │ each supervisor owns 3 micro-agents    │
          ▼                                        ▼
   .claude/skills/<team>-*                  vault/ + state.db
```

- **Command Center** (`synthesizer`, `orchestrator`) — the only agents allowed to
  write the daily plan. Everyone else executes against it.
- **Domain Supervisors** — one Claude Code subagent per team
  (`.claude/agents/*.md`). A supervisor doesn't do the work itself; it invokes
  its micro-agents (implemented as skills) and reports results back up.
- **Micro-agents** — implemented as Claude Code **skills**
  (`.claude/skills/<team>-<task>/SKILL.md`), not full agents. They are single
  purpose, stateless, and cheap to invoke repeatedly (e.g. once per quiz
  question, once per job posting).

## 2. Command Center

### 2.1 Synthesizer Agent (Data Aggregator) — `.claude/agents/synthesizer.md`

Role: Chief of Staff. Never executes tasks — only listens and summarizes.

| Micro-task | Skill | Reads | Writes |
|---|---|---|---|
| Log Parser | `synthesizer-log-parser` | `state.db` (`execution_logs`, `tasks`), Mentor quiz scores, GitHub commit data, Scout response rates | in-memory structured summary |
| State Updater | `synthesizer-state-updater` | summary above | `vault/outputs/briefings/YYYY-MM-DD.json` |

Output contract — the **Daily Briefing**:

```json
{
  "date": "2026-08-09",
  "learning": { "quizzes_passed": 3, "topics_weak": ["OAuth2.0"] },
  "engineering": { "commits": 4, "prs_reviewed": 1, "open_bugs": 2 },
  "opportunities": { "applications_sent": 2, "response_rate": 0.15 },
  "performance": { "coding_hours": 3.4, "velocity_delta_pct": -20, "burnout_risk": "low" },
  "radar": { "signals": ["Qdrant adoption up in Tier-2 AI job posts"] }
}
```

This file is the single handoff artifact between Synthesizer and Orchestrator —
it is also linked into `vault/wiki/` so it's queryable later.

### 2.2 Main Orchestrator (Task Planner) — `.claude/agents/orchestrator.md`

Role: CEO. Reads the latest briefing, decides what happens today.

| Micro-task | Skill | Behavior |
|---|---|---|
| Decomposer | `orchestrator-decomposer` | Breaks a goal (e.g. "Backend internship by May") into sub-goals with deadlines, written as rows in `tasks` |
| Scheduler | `orchestrator-scheduler` | Allocates time blocks against sub-goals, adjusted by Performance Team velocity data |
| Dispatcher | `orchestrator-dispatcher` | Sends the trigger prompt to the relevant Domain Supervisor agent and records the dispatch in `execution_logs` |

The Orchestrator is the only agent permitted to `INSERT`/`UPDATE` the `tasks`
table's `assigned_agent_id` and `status` columns — see [§5](#5-task-execution-state--sqlite).

## 3. Domain Supervisors

Each supervisor is a Claude Code subagent (`.claude/agents/<name>.md`) that owns
exactly three micro-agent skills. Supervisors are stateless between invocations;
all durable state goes to `state.db` or `vault/`.

| Supervisor | Micro-agents (skills) | Primary Mark-L touchpoint |
|---|---|---|
| **Mentor** (Learning) | `mentor-curriculum`, `mentor-concept-explainer`, `mentor-quiz-master` | none yet — net-new |
| **Architect** (Engineering) | `architect-system-designer`, `architect-code-reviewer`, `architect-debugger` | `actions/dev_agent.py`, `actions/code_helper.py`, `actions/screen_processor.py` (visual whiteboard/code review) |
| **Scout** (Opportunities) | `scout-web-scraper`, `scout-filter-agent`, `scout-networker` | `actions/web_search.py`, `actions/browser_control.py` |
| **Brand** (Presentation) | `brand-resume-tailor`, `brand-cover-letter-drafter`, `brand-portfolio-sync` | `actions/send_message.py`, `actions/file_processor.py` |
| **Interrogator** (Prep) | `interrogator-dsa`, `interrogator-system-design`, `interrogator-core-cs`, `interrogator-ml-genai`, `interrogator-behavioral` | none yet — net-new |

Design note: Interrogator has 5 micro-agents instead of 3 (DSA, System Design,
Core CS, ML/GenAI, Behavioral) — kept as specified rather than artificially
collapsed, since interview prep genuinely spans five distinct examiner
personas.

## 4. Support Supervisors

### 4.1 Performance Team (`.claude/agents/performance.md`)

Feeds the Synthesizer and Orchestrator directly — it's the COO, tracking pace
and bandwidth so the Orchestrator can reshuffle the schedule instead of letting
it silently slip.

| Micro-agent | Skill | Data source |
|---|---|---|
| Quantifier | `performance-quantifier` | WakaTime API, GitHub commit API, LeetCode API, `actions/system_monitor.py` |
| Analyst (Velocity Forecaster) | `performance-analyst` | `tasks` table (planned vs. actual duration), `execution_logs` |
| Wellness Monitor | `performance-wellness` | check-in sentiment, `actions/proactive.py` timing patterns (late-night session detection) |

The Wellness Monitor is the one micro-agent with **override authority**: if it
flags burnout risk, it can force the Orchestrator to insert a rest day ahead of
the normal scheduling pass. This is the single exception to "supervisors don't
write to the plan directly" and must stay logged in `execution_logs` for
auditability.

### 4.2 Radar Team (`.claude/agents/radar.md`)

Feeds Mentor and Architect — CTO function, keeps the curriculum and project
choices aligned with what Tier-2 backend/AI teams are actually adopting.

| Micro-agent | Skill | Data source |
|---|---|---|
| Signal Finder | `radar-signal-finder` | Hacker News, GitHub Trending, target-company eng blogs (via `actions/web_search.py`) |
| Stack Evaluator | `radar-stack-evaluator` | `vault/wiki/resume.md` vs. current market signals |
| Executive Summarizer | `radar-executive-summarizer` | compiles the week's signals into `vault/outputs/tech_briefings/` |

## 5. Task Execution State — SQLite

Deterministic engine, schema at [`state/schema.sql`](../state/schema.sql),
driven by [`orchestrator.py`](../orchestrator.py) at the repo root. No agent
trusts its own claim of success — only a `0` exit code recorded in
`execution_logs` counts as done. See [§7](#7-the-hallucination-loop).

```sql
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'idle'
);

CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    command TEXT DEFAULT '',            -- verification command for the Hallucination Loop
    assigned_agent_id TEXT,
    status TEXT DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    FOREIGN KEY(assigned_agent_id) REFERENCES agents(id)
);

CREATE TABLE task_dependencies (              -- the dependency graph
    task_id TEXT NOT NULL,
    depends_on_task_id TEXT NOT NULL,
    PRIMARY KEY (task_id, depends_on_task_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id)
);

CREATE TABLE execution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    command_run TEXT,
    exit_code INTEGER,
    stdout TEXT,
    stderr TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);
```

The 9 top-level agents (Synthesizer, Orchestrator, Mentor, Architect, Scout,
Brand, Interrogator, Performance, Radar) are seeded as rows in `agents`;
micro-agents are *not* separate rows — they're skills invoked in-process by
their supervisor and are attributed to the supervisor's `agent_id` in
`execution_logs`.

A task is **eligible for dispatch** when: `status='pending'`,
`retry_count < max_retries`, and every row in `task_dependencies` for that
task points at a task whose `status='done'` (a task with no dependency rows
is always eligible on that criterion). `orchestrator.py`'s `get_next_task()`
picks the oldest eligible task by `created_at`, runs its `command` as a
subprocess, and applies §7's Hallucination Loop to the result.

## 6. Knowledge Memory — Obsidian Vault

```
vault/
├── raw/       # unprocessed captures: transcripts, scraped postings, quiz results
├── wiki/      # distilled, graph-linked notes (one concept/project per file, [[wikilinks]])
└── outputs/   # everything JARVIS generates: briefings/, tech_briefings/, resumes/
```

Bridge to existing Mark-L memory: `memory/memory_manager.py` already implements
`long_term.json` (identity, preferences, projects, sessions, monitors) — that
file is the **short-term working memory** Gemini Live reads every session.
The vault is the **long-term graph memory** JARVIS OS agents read/write. Do not
merge the two files: `long_term.json` stays small and prompt-injectable;
`vault/` can grow unbounded because agents grep/search it rather than loading
it whole.

## 7. The Hallucination Loop

The Orchestrator wraps every dispatched task in a verification script that
only trusts the terminal's exit code:

```python
result = subprocess.run(command, capture_output=True, text=True)
passed = result.returncode == 0
```

An agent's own narrative ("I fixed it", "tests should pass now") is never
sufficient to mark a `tasks` row `done`. Only `execution_logs.exit_code == 0`
for the task's verification command does. On failure, `retry_count` increments
and the task is re-dispatched until `max_retries` is hit, at which point the
Orchestrator escalates it into the next Daily Briefing instead of silently
retrying forever.

## 8. Mark-L Integration (OS Bridge)

JARVIS OS does not reimplement voice/vision/system control — it dispatches
into the existing Mark-L action layer:

| JARVIS OS need | Existing Mark-L module |
|---|---|
| Real-time voice (Gemini Live) | `main.py`, `core/` |
| System & desktop control | `actions/computer_control.py`, `actions/desktop.py`, `actions/open_app.py` |
| Visual awareness (screen/webcam) | `actions/screen_processor.py` — used by Architect for "seeing" whiteboards/code |
| Dynamic content panel | `ui.py` HUD + `dashboard/` |
| OS-native scheduled notifications | `actions/reminder.py` — fires when a task gets `blocked` (see below), and used by Orchestrator's Scheduler for time-block reminders |
| Persistent memory bridge | `memory/memory_manager.py` ↔ `vault/` (see §6) |
| Background/topic watching | `actions/background_monitor.py` — reused by Radar's Signal Finder |
| Autonomous dev tasks | `actions/dev_agent.py`, `actions/code_helper.py` — reused by Architect |

### 8.1 The wiring, concretely — `core/jarvis_os_bridge.py`

This module is the actual OS Bridge; `main.py` never talks to
`orchestrator.py` or `vault/` directly. It's a thin layer over already-tested
functions — it never re-implements the dispatch/verify/hallucination-loop
logic in `orchestrator.py`, only consumes it:

- `run_orchestrator_cycle()` — connects to `state/orchestrator.db`, calls
  `orchestrator.drain()`, and returns `{done, blocked, requeued}`. Any task
  that ends up `blocked` (retries exhausted) raises a real OS-native
  reminder via `actions/reminder.py` — the escalation this spec's §7
  describes isn't just a DB row, it surfaces as an actual notification.
- `write_task_summary()` — for every task that reaches a terminal state
  (`done` or `blocked`) in a cycle, writes
  `vault/outputs/task_summaries/<task_id>.md` sourced from that task's
  `execution_logs` row (command, exit code, stdout, stderr) — never a
  re-narrated claim, only what the Hallucination Loop actually verified.
- `sync_memory_to_vault()` — one-way distillation of
  `memory/long_term.json` into `vault/wiki/mark_l_memory.md` on every cycle.
- `get_todays_briefing()` / `format_briefing_for_speech()` — reads the
  Synthesizer's Daily Briefing (§2.1) if one exists for today and turns it
  into a sentence Gemini can speak.
- `init_orchestrator_db()` / `get_task_board()` /
  `format_task_board_oneline()` / `format_task_board_for_panel()` — startup
  and rendering helpers (§8.2): create the DB if it doesn't exist yet, and
  read a point-in-time snapshot (`{counts, tasks}`, most-recently-updated 20
  tasks) formatted for the HUD log line and the content panel respectively.
  Read-only — never dispatches anything.

`main.py` wires this in three places:

- **Startup** — `JarvisSession.run()` calls `await self._init_jarvis_os()`
  as its very first action, before the dashboard or the connect/reconnect
  loop. That method calls `init_orchestrator_db()` (creating
  `state/orchestrator.db` from `state/schema.sql` on first run — idempotent
  after that) and then renders the current task board once via
  `_render_jarvis_os_panel()`, so the HUD shows real state before the voice
  session is even up.
- **Background loop** — `_run_jarvis_os_orchestrator()`, an `async def`
  method registered in the same `asyncio.TaskGroup` as
  `_run_background_monitor()` and `_run_proactive_mode()`. Every 30 minutes
  (after a 10-minute startup delay) it syncs the vault, drains the
  orchestrator, re-renders the panel via `_render_jarvis_os_panel()` — so
  the board stays live as retries/dispatches happen, not just a one-time
  boot snapshot — and, only if something was actually verified done or
  blocked (never on a bare retry), hands Gemini a short factual summary to
  narrate in the user's language, gated by the same
  speaking/recent-speech checks `_run_background_monitor` already uses so it
  never interrupts.
- **Voice tool** — the `jarvis_os` tool declaration
  (`run | status | sync_vault | briefing`), dispatched in `_execute_tool`
  exactly like every other tool (`open_app`, `reminder`, etc.): the user can
  say "run my background tasks" or "what's my JARVIS OS status" and get a
  live answer.

No new voice/vision/system-control code was written to make this work; the
bridge only calls into `actions/reminder.py`, `memory/memory_manager.py`,
`ui.py`'s existing thread-safe `write_log`/`show_content` calls, and
`orchestrator.py`.

### 8.2 HUD / content panel rendering

`_render_jarvis_os_panel()` (in `main.py`) is the single place that turns a
task-board snapshot into what the user actually sees, calling the exact same
thread-safe `JarvisUI` methods every other tool already uses
(`ui.write_log`, `ui.show_content` — see `web_search`'s
`self.ui.show_content(_label, r)` for the established pattern):

- `ui.write_log(...)` — one compact line on the HUD's scrolling log panel,
  e.g. `SYS: JARVIS OS — 2 pending, 1 done, 1 blocked`.
- `ui.show_content("JARVIS OS", ...)` — the fuller board in the content
  panel below the HUD: per-status counts, up to 20 most-recently-updated
  tasks with a status marker (`[ ]` pending, `[~]` in progress, `[x]` done,
  `[!]` blocked), and today's Daily Briefing if the synthesizer has written
  one, or an explicit "none yet" line if not.

## 9. Directory Map (post-scaffold)

```
Mark-L-main/
├── .claude/
│   ├── agents/         # 9 supervisor subagent definitions
│   └── skills/         # micro-agent skills, one dir per skill
├── specs/
│   └── JARVIS_OS.md     # this file
├── orchestrator.py       # deterministic task engine (drain/watch, hallucination loop)
├── state/
│   ├── schema.sql        # SQLite task-execution schema
│   └── orchestrator.db   # created on first run — not committed
├── vault/
│   ├── raw/
│   ├── wiki/              # includes mark_l_memory.md, synced from long_term.json
│   └── outputs/
├── actions/               # existing Mark-L capabilities (unchanged)
├── core/
│   ├── jarvis_os_bridge.py  # NEW — orchestrator ↔ Mark-L (voice/reminders/vault) bridge
│   └── ...                   # existing Gemini Live session core (unchanged)
├── memory/                # existing long_term.json bridge (unchanged)
└── dashboard/              # existing remote dashboard (unchanged)
```

## 10. Open Items / Not Yet Built

This spec and its `.claude/agents` + `.claude/skills` scaffolding describe
*intended* structure and contracts. As of this revision:

**Built and verified:**
- `orchestrator.py` connects to `state/orchestrator.db`, resolves the
  dependency graph (`task_dependencies`), and runs the Hallucination Loop —
  tested end-to-end (§5, §7).
- `core/jarvis_os_bridge.py` wires that engine into `main.py`: a voice tool
  (`jarvis_os`: run/status/sync_vault/briefing/roster/assign), a background
  heartbeat (`_run_jarvis_os_orchestrator`) that wakes every 60s and drains
  tasks, syncs `memory/long_term.json` into `vault/wiki/`, raises a real OS
  reminder on `blocked` tasks, and narrates verified outcomes through the
  voice session (§8.1), and per-task markdown summaries in
  `vault/outputs/task_summaries/` for every task that reaches `done` or
  `blocked` (§8.1).
- Fully autonomous heartbeat: `_run_jarvis_os_orchestrator` and a separate
  `_run_jarvis_os_panel_refresh` (10s cadence) are started once from
  `run()` as standalone `asyncio.create_task`s, not inside the
  per-connection `TaskGroup` — they keep running across reconnects and even
  while no live voice session is active, so pending tasks execute without a
  manual `jarvis_os run` trigger.
- Startup wiring (§8.2): `JarvisSession.run()` initializes
  `state/orchestrator.db` before anything else starts, and renders the live
  task board — plus today's Daily Briefing if one exists — onto both the
  HUD log line and the content panel (`_init_jarvis_os`,
  `_render_jarvis_os_panel`), refreshed on both the 60s drain cycle and the
  10s panel-refresh loop so it stays current rather than a one-time boot
  snapshot.
- Team roll call (§8.2): `get_agent_roll_call`/`format_agent_roll_call` in
  `core/jarvis_os_bridge.py` report every supervisor's live status plus its
  most recently verified task, rendered in the content panel with a
  high-visibility marker per state (`[ ⚡ EXECUTING ]` while `busy`,
  `[ 🔴 BLOCKED ]`, `[ 🟢 IDLE ]`) and speakable via the `jarvis_os` voice
  action `roster` ("assemble the team").
- Automatic sub-agent dispatch (closes the gap formerly noted here): a
  `tasks` row with `agent_prompt` set and `assigned_agent_id` in
  `orchestrator.py`'s `AUTO_DISPATCH_AGENTS` (`mentor`, `brand`,
  `interrogator`, `scout`, `radar` — the 5 supervisors with no Bash in their
  tool list) gets handed to a headless `claude -p` call
  (`run_claude_agent`), tool-restricted to strip Bash regardless, before its
  `command` runs. `architect`/`orchestrator`/`performance`/`synthesizer`
  (all Bash-capable) are excluded from auto-dispatch on purpose and stay
  manual-only. Crucially this does **not** loosen the Hallucination Loop:
  the agent's own output is logged to `execution_logs` for audit but never
  decides `done`/`blocked` — the task's `command` exit code still does, same
  as before. `orchestrator.add_task()` is the programmatic entry point for
  handing JARVIS OS such a task.

**Not yet implemented:**
- Nothing yet *populates* `agent_prompt` tasks automatically — the Command
  Center agents (`synthesizer`/`orchestrator`, or `orchestrator-decomposer`)
  still aren't invoked on a schedule to decide what work to hand the auto-
  dispatch agents. `orchestrator.add_task()` exists and is exercised by
  tests, but something (a cron-like trigger, or the Orchestrator agent
  itself) still needs to call it — `state/orchestrator.db` starts empty
  until it does.
- Web scraping (Scout, Radar) has no client code yet. Performance's
  GitHub/LeetCode pulls now have credentialed client code
  (`actions/github_integration.py`, reading GITHUB_TOKEN/GITHUB_USERNAME/
  LEETCODE_USERNAME from `.env`) — WakaTime is still unwired.
- `vault/raw/` and `vault/outputs/briefings/` are still scaffolded empty —
  nothing populates them automatically yet; only `vault/wiki/mark_l_memory.md`
  and `vault/outputs/task_summaries/` are written for real, by the
  background loop.

Treat this as the target architecture to build toward incrementally, not a
description of fully autonomous operation today.
