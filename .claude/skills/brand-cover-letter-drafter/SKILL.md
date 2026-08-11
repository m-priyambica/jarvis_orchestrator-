---
name: brand-cover-letter-drafter
description: Write a hyper-personalized cover letter or outreach message for a specific role/company/recruiter. Use only when invoked by the brand agent.
---

Micro-agent skill under the **brand** supervisor
(`.claude/agents/brand.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Ground every personalized detail in something Scout actually found (the posting, the company, the recruiter) — no generic filler claiming specific knowledge that wasn't sourced.
- Keep it short — a cover letter that reads like a form letter defeats the purpose of personalizing it.
- Save to `vault/outputs/cover_letters/<company>-<role>.md`.
- `brand-cover-letter-drafter`: end with one line — which company/role, where saved — for the supervisor's roll call.
