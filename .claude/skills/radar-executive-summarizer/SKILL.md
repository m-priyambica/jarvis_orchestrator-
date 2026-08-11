---
name: radar-executive-summarizer
description: Compile the week's signals into a crisp, personalized Sunday Tech Briefing. Use only when invoked by the radar agent.
---

Micro-agent skill under the **radar** supervisor
(`.claude/agents/radar.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Input: the week's accumulated `radar-signal-finder` and `radar-stack-evaluator` output.
- Output: `vault/outputs/tech_briefings/YYYY-Www.md`, a ~3-minute read — optimize for signal density, not a link dump.
- Every item should say concretely why it matters for this specific job hunt, not just what happened.
- `radar-executive-summarizer`: end with one line — signal count compiled, where saved — for the supervisor's roll call.
