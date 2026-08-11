---
name: scout-web-scraper
description: Find fresh job postings from company career pages. Use only when invoked by the scout agent.
---

Micro-agent skill under the **scout** supervisor
(`.claude/agents/scout.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- No scraping client/credentials exist yet (`specs/JARVIS_OS.md` §10) — use `WebSearch`/`WebFetch` against public career pages, don't claim a scraper pipeline is running.
- Target Tier-2 Backend/AI companies by default (e.g. Atlassian, Swiggy, Razorpay) unless told otherwise.
- Write found postings to `vault/raw/postings/` with source URL and date found — never fabricate a posting.
- `scout-web-scraper`: end with one line — how many postings found — for the supervisor's roll call.
