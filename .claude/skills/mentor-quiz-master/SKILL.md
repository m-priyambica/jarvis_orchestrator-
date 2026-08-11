---
name: mentor-quiz-master
description: Generate multiple-choice and short-answer questions to test retention on recently studied material, and grade the answers. Use only when invoked by the mentor agent.
---

Micro-agent skill under the **mentor** supervisor
(`.claude/agents/mentor.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Input: a topic or `vault/wiki/` note that was recently studied.
- Output: a short quiz, then score the user's answers and identify specific weak points (not just a pass/fail).
- Write results to `vault/raw/quizzes/` so `synthesizer-log-parser` can pick up weak topics.
- `mentor-quiz-master`: end with one line — score and weak points found — for the supervisor's roll call.
