---
name: architect-debugger
description: Analyze a stack trace or error log and explain root cause before suggesting a fix. Use only when invoked by the architect agent.
---

Micro-agent skill under the **architect** supervisor
(`.claude/agents/architect.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Read the actual traceback/log — don't guess at the bug from the symptom description alone if the raw log is available.
- State root cause explicitly, then propose a fix; never skip straight to a patch without the diagnosis.
- If screen/webcam vision is needed to see the user's error (whiteboard, IDE), route through `actions/screen_processor.py`.
- `architect-debugger`: end with one line — root cause found, or "inconclusive" — for the supervisor's roll call.
