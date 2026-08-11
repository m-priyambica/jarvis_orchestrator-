---
name: brand-resume-tailor
description: Rewrite master resume bullet points to index on keywords a specific job description needs. Use only when invoked by the brand agent.
---

Micro-agent skill under the **brand** supervisor
(`.claude/agents/brand.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Input: keywords/gaps from `scout-filter-agent`'s scoring, and the master resume at `vault/wiki/resume.md`.
- Reframe and reprioritize existing bullets only — never invent experience that isn't in the master resume.
- Save the tailored version to `vault/outputs/resumes/<company>-<role>.md`.
- `brand-resume-tailor`: end with one line — which company/role, where saved — for the supervisor's roll call.
