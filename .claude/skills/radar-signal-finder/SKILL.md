---
name: radar-signal-finder
description: Scan Hacker News, GitHub Trending, and target companies' engineering blogs for genuine shifts in backend/AI infrastructure. Use only when invoked by the radar agent.
---

Micro-agent skill under the **radar** supervisor
(`.claude/agents/radar.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Use `WebSearch`/`WebFetch`, mirroring the pattern in `actions/web_search.py`.
- Filter noise — flag genuine adoption shifts, not every trending repo or hype post.
- Every flagged signal needs a concrete source (specific post/repo/blog entry).
- `radar-signal-finder`: end with one line — how many genuine signals found — for the supervisor's roll call.
