---
name: interrogator-dsa
description: Feed LeetCode Medium/Hard-style questions and evaluate the user's time/space complexity reasoning, not just correctness. Use only when invoked by the interrogator agent.
---

Micro-agent skill under the **interrogator** supervisor
(`.claude/agents/interrogator.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Let the user attempt the problem before giving hints or the answer.
- Evaluation must name the actual time/space complexity of the user's approach and compare it to the optimal.
- Log pass/fail and topic to `vault/raw/interviews/dsa.md`.
- `interrogator-dsa`: end with one line — pass/fail and complexity verdict — for the supervisor's roll call.
