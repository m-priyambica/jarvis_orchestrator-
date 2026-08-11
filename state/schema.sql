-- JARVIS OS deterministic task-execution schema.
-- See specs/JARVIS_OS.md §5 for the full contract.
--
-- Wired into orchestrator.py (repo root) — that script connects to
-- state/orchestrator.db, applies this file if the DB is fresh, and runs the
-- deterministic dispatch/verify loop. To initialize by hand instead:
--   sqlite3 state/orchestrator.db < state/schema.sql
--
-- Only the orchestrator (agent or orchestrator.py) writes
-- tasks.assigned_agent_id / tasks.status. No agent's own narrative counts as
-- success — only a 0 exit_code recorded in execution_logs justifies
-- status='done' (the "Hallucination Loop").
--
-- Extends the tables originally listed in specs/JARVIS_OS.md §5 with:
--   - tasks.command            the verification command run to prove a task
--                               is actually done (subprocess exit code, not
--                               an agent's say-so)
--   - tasks.agent_prompt        if set AND assigned_agent_id is one of the
--                               Bash-free supervisors (mentor/brand/
--                               interrogator/scout/radar — see
--                               orchestrator.py's AUTO_DISPATCH_AGENTS),
--                               orchestrator.py hands this to a headless
--                               `claude -p` call as the actual *work* before
--                               running `command`. The agent's own output is
--                               logged but never decides done/blocked —
--                               `command`'s exit code still does, same as
--                               every other task (spec §7/§10).
--   - task_dependencies         the dependency graph a task's readiness is
--                               computed from (see get_next_task in
--                               orchestrator.py) — a task is only eligible
--                               once every task it depends on is 'done'
--   - tasks.status='awaiting_approval'   a drafted task the orchestrator will
--                               NOT dispatch (get_next_task only ever selects
--                               'pending') until a human explicitly approves
--                               it — see orchestrator.approve_plan(). This is
--                               the Meta-Agent approval workflow: JARVIS can
--                               draft a multi-step plan without being able to
--                               make it *run* on its own say-so.
--   - tasks.plan_id             groups every task row belonging to one
--                               drafted plan (e.g. a multi-day prep
--                               schedule) so they can be approved together
--                               by orchestrator.approve_plan(plan_id)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS agents (
    id                      TEXT PRIMARY KEY,
    name                    TEXT NOT NULL,
    status                  TEXT DEFAULT 'idle' CHECK (status IN ('idle', 'busy', 'blocked')),
    -- Best-effort file path / URL the agent's current task command or
    -- agent_prompt references (see orchestrator._extract_reference) — feeds
    -- the 3D UI's per-agent "what is it touching right now" display. Not
    -- live syscall/file-handle tracing: tasks run as opaque subprocesses or
    -- headless `claude -p` calls whose internal tool use isn't observable
    -- from here, so this is a heuristic text scan, not a guarantee.
    current_file_reference TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tasks (
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

CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id             TEXT NOT NULL,
    depends_on_task_id  TEXT NOT NULL,
    PRIMARY KEY (task_id, depends_on_task_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id),
    CHECK (task_id != depends_on_task_id)
);

CREATE TABLE IF NOT EXISTS execution_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      TEXT NOT NULL,
    command_run  TEXT,
    exit_code    INTEGER,
    stdout       TEXT,
    stderr       TEXT,
    logged_at    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(assigned_agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_plan ON tasks(plan_id);
CREATE INDEX IF NOT EXISTS idx_execution_logs_task ON execution_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_dependencies_dep ON task_dependencies(depends_on_task_id);

-- Seed the 9 Command Center / Domain / Support supervisor agents.
-- Micro-agents (skills) are NOT separate rows here — they execute in-process
-- under their supervisor and are attributed to the supervisor's id in
-- execution_logs.command_run.
INSERT OR IGNORE INTO agents (id, name) VALUES
    ('synthesizer',  'Synthesizer'),
    ('orchestrator', 'Main Orchestrator'),
    ('mentor',       'Mentor Team'),
    ('architect',    'Architect Team'),
    ('scout',        'Scout Team'),
    ('brand',        'Brand Team'),
    ('interrogator', 'Interrogator Team'),
    ('performance',  'Performance Team'),
    ('radar',        'Radar Team');
