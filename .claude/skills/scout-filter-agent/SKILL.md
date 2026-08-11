---
name: scout-filter-agent
description: Score a job description out of 100 against the user's current skills and goals. Use only when invoked by the scout agent.
---

Micro-agent skill under the **scout** supervisor
(`.claude/agents/scout.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Read `vault/wiki/resume.md` for current skills; default goal is Tier-2 Backend/AI roles unless told otherwise.
- Score must come with a stated rationale: skills matched, skills missing, seniority fit.
- Feed high scorers to the brand agent's `brand-resume-tailor` for tailoring, not just a bare number back to the user.
- `scout-filter-agent`: end with one line — score and top reason — for the supervisor's roll call.
