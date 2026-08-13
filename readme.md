# JARVIS Orchestrator

A deterministic multi-agent orchestration layer for automating learning, software engineering, and job hunting — built on top of [Mark-L](https://github.com/FatihMakes/Mark-L) for voice, vision, and system control.

> **Attribution:** The voice assistant runtime (`main.py`, `ui.py`, `actions/`, `core/`) is [Mark-L by FatihMakes](https://github.com/FatihMakes/Mark-L), used here as the execution layer under its [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) license. **JARVIS Orchestrator** — the orchestration layer, state machine, and 9-agent hierarchy described below — is my own design, built on top of it.

---

## Why this exists

LLM agents lose state. They hallucinate task completion, forget what happened five minutes ago when a context window resets, and report success even when nothing actually ran. JARVIS Orchestrator exists to solve that: instead of trusting an agent's self-report, it wraps every task in a deterministic state machine that only trusts one thing — the terminal's exit code.

```python
if result.returncode == 0:
    task PASSES
else:
    log stderr, retry (up to 3x)
```

If a task fails after its retries, it's marked `blocked` and escalated — never silently swallowed, never assumed complete.

---

## Architecture

### Command Center (top layer)
- **Synthesizer** — aggregates data from every team into a structured "Daily Briefing"
- **Main Orchestrator** — plans, schedules, and dispatches tasks to the Domain Teams

### Domain Teams (7 supervisors, each managing single-purpose micro-agents)
| Team | Focus |
|---|---|
| Mentor | Learning — curriculum generation, concept explanation, quizzing |
| Architect | Engineering — system design, code review, debugging |
| Scout | Opportunities — job scraping, scoring, recruiter outreach |
| Brand | Presentation — resume tailoring, cover letters, portfolio sync |
| Interrogator | Interview prep — DSA, system design, CS fundamentals, behavioral |
| Performance | Progress tracking — metrics, velocity forecasting, burnout detection |
| Radar | Emerging tech — trend scraping, stack evaluation, weekly briefings |

### State & Verification
- **SQLite state machine** (`state/schema.sql`) — tasks, retry counts, execution logs, dependency graphs. Nothing is trusted to an LLM's memory.
- **Deterministic verification** — every task is checked by exit code, not by asking an agent if it succeeded.
- **Bash-access restriction** — only a subset of supervisors are allowed to auto-dispatch through unattended execution. Agents capable of running arbitrary shell commands remain manual-only, invoked directly rather than woken up on a schedule.

### Knowledge base
An Obsidian Markdown Vault (`vault/`) — `raw/` for captured data, `wiki/` for distilled notes, `outputs/` for generated task summaries — gives every agent a shared, persistent memory that survives context resets.

---

## Project structure

Two layers live side by side: the Mark-L voice assistant runtime, and the JARVIS Orchestrator agent layer built on top of it. `core/jarvis_os_bridge.py` is the only seam between them.

```
jarvis_os/
│
│  ── Mark-L runtime (not mine — see Attribution) ──
├── main.py, ui.py, setup.py
├── actions/           # web search, screen capture, system control, etc.
├── core/               # Gemini client, STT/TTS, jarvis_os_bridge.py
├── memory/             # long_term.json — sessions, monitors, identity
├── dashboard/           # FastAPI remote control
│
│  ── JARVIS Orchestrator agent layer (mine) ──
├── orchestrator.py      # Deterministic task engine — dependency graph + hallucination loop
├── state/
│   ├── schema.sql        # SQLite task-execution schema
│   └── verify_task.py     # Verification — proves an agent produced a real artifact
├── .claude/
│   ├── agents/            # 9 supervisor subagent definitions
│   └── skills/             # micro-agent skills, one per capability
├── vault/                  # Obsidian knowledge base
├── test_integration.py      # End-to-end smoke test
├── test_smoke_audit.py        # Headless audit — import + consistency checks
│
└── specs/JARVIS_OS.md          # Full architecture spec
```

---

## Running it

### Requirements
- Python 3.11 or 3.12
- A desktop session (display + audio) for the full Mark-L voice/vision runtime
- A Gemini API key in `config/api_keys.json`:
  ```json
  { "gemini_api_key": "YOUR_KEY_HERE" }
  ```

### Quick start
```bash
git clone https://github.com/m-priyambica/jarvis_os.git
cd jarvis_os
pip install -r requirements.txt
python main.py
```

### Headless / CI testing
The full voice/vision runtime needs a real display and microphone, but the orchestration layer can be tested headlessly:

```bash
sudo apt-get install -y xvfb python3-tk
python3 -m pip install -r requirements.txt

xvfb-run -a python3 test_integration.py     # end-to-end dry run, FakeUI, no mic/camera/API needed
python3 -m pytest -q test_smoke_audit.py    # import + agent-roster consistency audit
```

---

## Known limitations

- The Mark-L voice/vision loop, real PyQt6 rendering, and browser/desktop automation require a full desktop environment — not testable in a bare container.
- Only 5 of the 9 supervisors (Mentor, Brand, Interrogator, Scout, Radar) currently auto-dispatch through the headless Claude CLI; the rest declare Bash access and stay manual-only by design, not by bug.
- `vault/raw/` is scaffolded but not yet populated — the Synthesizer's data-aggregation pipeline is still in progress.

---

## License

The JARVIS Orchestrator orchestration layer follows the same **[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)** terms as the Mark-L runtime it's built on — personal and non-commercial use only, with attribution.
