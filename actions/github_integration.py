#github_integration.py
"""GitHub + LeetCode metrics for JARVIS OS's performance tracking
(specs/JARVIS_OS.md §4/§10 — Performance team's Quantifier data sources).

Previously these calls (where anything called them at all) went out
unauthenticated, so GitHub's anonymous rate limit turned them into 401/403s
almost immediately — which is what showed up as background tasks going
'blocked' after orchestrator.py's Hallucination Loop exhausted retries.
This module actually loads GITHUB_TOKEN / GITHUB_USERNAME / LEETCODE_USERNAME
and sends the token in the Authorization header.
"""
import os
import sys
from pathlib import Path

import requests

BASE_DIR     = Path(__file__).resolve().parent.parent
GITHUB_API   = "https://api.github.com"
LEETCODE_API = "https://leetcode.com/graphql"


def _load_dotenv() -> None:
    """Populate os.environ from a .env file at the repo root, if present.
    Nothing else in this codebase loads .env yet (python-dotenv isn't a
    dependency) — without this, GITHUB_TOKEN etc. sit in .env but os.getenv()
    never sees them. Never overwrites a variable already set in the real
    environment.
    """
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

GITHUB_TOKEN      = os.getenv("GITHUB_TOKEN", "")
GITHUB_USERNAME   = os.getenv("GITHUB_USERNAME", "")
LEETCODE_USERNAME = os.getenv("LEETCODE_USERNAME", "")


def _github_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def get_recent_commits(username: str = "", limit: int = 10) -> dict:
    """Recent public push activity for a GitHub user via the Events API."""
    username = (username or GITHUB_USERNAME).strip()
    if not username:
        return {"ok": False, "error": "no GitHub username configured (set GITHUB_USERNAME)"}
    if not GITHUB_TOKEN:
        return {"ok": False, "error": "no GITHUB_TOKEN set — request will hit GitHub's low anonymous rate limit"}

    resp = requests.get(
        f"{GITHUB_API}/users/{username}/events/public",
        headers=_github_headers(),
        params={"per_page": limit},
        timeout=15,
    )
    if resp.status_code == 401:
        return {"ok": False, "error": "GitHub rejected GITHUB_TOKEN (401) — it may be expired or revoked"}
    if resp.status_code == 403:
        return {"ok": False, "error": "GitHub rate-limited this request (403)"}
    resp.raise_for_status()

    commits = []
    for event in resp.json():
        if event.get("type") != "PushEvent":
            continue
        for c in event.get("payload", {}).get("commits", []):
            commits.append({
                "repo":    event.get("repo", {}).get("name", ""),
                "message": c.get("message", ""),
                "sha":     c.get("sha", "")[:7],
                "at":      event.get("created_at", ""),
            })
    return {"ok": True, "username": username, "commits": commits[:limit]}


def get_commit_count(username: str = "", days: int = 7) -> dict:
    """Approx commit count in the last N days. GitHub's REST API has no
    direct commit-count endpoint without GraphQL + a repo-scoped PAT, so this
    counts push events from the same recent-activity feed as
    get_recent_commits instead.
    """
    result = get_recent_commits(username, limit=100)
    if not result.get("ok"):
        return result

    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    count = 0
    for c in result["commits"]:
        try:
            ts = datetime.fromisoformat(c["at"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts >= cutoff:
            count += 1
    return {"ok": True, "username": result["username"], "days": days, "commit_count": count}


def get_leetcode_progress(username: str = "") -> dict:
    """LeetCode's public GraphQL endpoint — no auth token required, just the
    username (LEETCODE_USERNAME)."""
    username = (username or LEETCODE_USERNAME).strip()
    if not username:
        return {"ok": False, "error": "no LeetCode username configured (set LEETCODE_USERNAME)"}

    query = {
        "query": """
            query userProblemsSolved($username: String!) {
              matchedUser(username: $username) {
                submitStatsGlobal { acSubmissionNum { difficulty count } }
              }
            }
        """,
        "variables": {"username": username},
    }
    resp = requests.post(LEETCODE_API, json=query, timeout=15)
    resp.raise_for_status()
    matched = (resp.json().get("data") or {}).get("matchedUser")
    if not matched:
        return {"ok": False, "error": f"no LeetCode user found for '{username}'"}

    stats = {row["difficulty"]: row["count"] for row in matched["submitStatsGlobal"]["acSubmissionNum"]}
    return {"ok": True, "username": username, "solved": stats}


def github_integration(parameters: dict = None, response=None, player=None, session_memory=None) -> str:
    """Public entry point, same (parameters/response/player/session_memory)
    calling convention as the other actions/ modules."""
    params   = parameters or {}
    action   = (params.get("action") or "commits").lower().strip()
    username = params.get("username", "")

    if action == "commits":
        result = get_recent_commits(username)
    elif action == "commit_count":
        result = get_commit_count(username, days=int(params.get("days", 7)))
    elif action == "leetcode":
        result = get_leetcode_progress(username)
    else:
        return f"Unknown github_integration action: {action}"

    if not result.get("ok"):
        return f"GitHub/LeetCode integration failed: {result['error']}"
    return str(result)


if __name__ == "__main__":
    # Usable directly as an orchestrator task's verification `command`, e.g.
    #   python actions/github_integration.py commit_count
    action = sys.argv[1] if len(sys.argv) > 1 else "commits"
    out = github_integration({"action": action})
    print(out)
    sys.exit(0 if "failed" not in out.lower() else 1)
