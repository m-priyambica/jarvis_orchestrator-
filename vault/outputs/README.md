# vault/outputs

Everything JARVIS OS generates as a finished artifact lives here, so nothing
an agent produces is a one-off the user can't find again.

Expected subfolders (created on demand by the agents/scripts that populate them):

- `briefings/` — Daily Briefing JSON from the synthesizer agent (`YYYY-MM-DD.json`)
- `tech_briefings/` — weekly Sunday Tech Briefing from the radar agent (`YYYY-Www.md`)
- `resumes/` — tailored resumes from the brand agent
- `cover_letters/` — drafted outreach/cover letters from the brand agent
- `portfolio_syncs/` — records of portfolio/README updates from the brand agent
- `task_summaries/` — **live, not aspirational** — `<task_id>.md` per task that
  reaches a terminal state (`done` or `blocked`), written by
  `core/jarvis_os_bridge.py`'s `write_task_summary()` every orchestrator
  cycle. Sourced from `execution_logs`, so it only ever repeats what the
  Hallucination Loop actually verified via exit code — command run, exit
  code, stdout/stderr. Overwritten on each new terminal attempt for that
  task id.

See `specs/JARVIS_OS.md` §6, §8.1.
