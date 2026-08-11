---
name: mentor-curriculum
description: Generate a syllabus/learning plan from a target job description or stated learning goal. Use only when invoked by the mentor agent.
---

Micro-agent skill under the **mentor** supervisor
(`.claude/agents/mentor.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Input: a target role/job description, or an explicit topic goal; check `vault/wiki/resume.md` and the latest Radar signals for grounding first.
- Output: an ordered syllabus written to `vault/wiki/curriculum-<topic>.md`, broken into modules with rough time estimates.
- Don't invent a syllabus in a vacuum — anchor each module to a specific skill gap or job requirement.
- `mentor-curriculum`: end with one line — topic and module count — for the supervisor's roll call.
