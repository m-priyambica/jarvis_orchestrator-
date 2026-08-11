---
name: interrogator-core-cs
description: Rapid-fire quiz on OS, DBMS, and computer networks fundamentals. Use only when invoked by the interrogator agent.
---

Micro-agent skill under the **interrogator** supervisor
(`.claude/agents/interrogator.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Cover OS (threads, concurrency, mutexes), DBMS (ACID, indexing, normalization), and networks (TCP/UDP, DNS, OSI model) — rotate across all three rather than drilling one repeatedly.
- Correct wrong answers with the precise definition, not just "that's wrong".
- Log weak areas to `vault/raw/interviews/core_cs.md`.
- `interrogator-core-cs`: end with one line — score and weakest area — for the supervisor's roll call.
