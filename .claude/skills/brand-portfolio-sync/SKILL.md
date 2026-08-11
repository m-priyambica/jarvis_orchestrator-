---
name: brand-portfolio-sync
description: Update the personal website or GitHub READMEs when a project is completed. Use only when invoked by the brand agent.
---

Micro-agent skill under the **brand** supervisor
(`.claude/agents/brand.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Reuse `actions/file_processor.py` for local file/document work and `actions/send_message.py` for any messaging step, rather than reimplementing file or messaging I/O.
- Confirm the project is actually complete (check its `tasks` status) before syncing — don't publish an in-progress project as finished.
- Save a record of what changed to `vault/outputs/portfolio_syncs/`.
- `brand-portfolio-sync`: end with one line — what was synced, or "skipped — project not done" — for the supervisor's roll call.
