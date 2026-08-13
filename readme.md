# ⚙️ MARK L (50)
### The Ultimate Cross-Platform Personal AI Assistant — By FatihMakes

> 📺 **[Watch the full setup video on YouTube](https://www.youtube.com/@FatihMakes)**

A real-time voice AI that can hear, see, understand, and control your computer — on any OS. Supports Windows, macOS, and Linux. Built on the Gemini Live API for native audio streaming, delivering zero subscriptions and total digital autonomy.

---

## ✨ Overview

MARK L is where the assistant stops being a tool and starts being a presence. It remembers yesterday's conversation, watches the topics you care about, and speaks first when it has something worth saying. The goal of this build was continuity — JARVIS should feel like it never fully left, even after you close it.

It's not just an assistant — it's an extension of your digital life.

---

## 🚀 Capabilities

### Core Features
| Feature | Description |
|---|---|
| 🎙️ Real-time Voice | Ultra-low latency conversation in any language via Gemini Live API |
| 🖥️ System Control | Launch apps, adjust volume/brightness, WiFi, shortcuts, power — all by voice |
| 🧩 Autonomous Tasks | High-level planning for complex multi-step goals via agent mode |
| 👁️ Visual Awareness | Real-time screen capture and webcam vision piped into your main Gemini session |
| 🧠 Persistent Memory | Deeply remembers projects, preferences, and personal context across sessions |
| ⌨️ Hybrid Input | Seamlessly switch between keyboard typing and voice commands |
| 🌅 Morning Briefing | On first boot: greets you, reads the time, recaps yesterday, and fetches live news |
| 🔔 Proactive 2.0 | Time-aware, context-aware check-ins — knows the time of day, your projects, and what you've been discussing |
| 🗓️ Session Memory | Summarises each conversation and mentions it naturally next morning — consumed after use, never repeats |
| 👁️‍🗨️ Background Monitoring | User-configured topic watching — checks for new headlines once a day and alerts naturally |
| 📊 Hardware Monitoring | Continuous CPU, RAM, GPU and temperature telemetry with localized voice alerts |
| 🌤️ Weather Report | Live weather data for your city, personalized from memory |
| 🗺️ Dynamic Content Panel | Scrollable display layer beneath the HUD that renders web results, news, and search data |
| 🔍 Multi-Mode Web Search | `news` / `research` / `price` / `compare` / `search` — Gemini Grounded first, DDG fallback |
| ⏰ Smart Reminders | OS-native scheduled notifications (Windows Task Scheduler / macOS LaunchAgent / Linux systemd) |
| ✈️ Flight Finder | Live flight price and availability lookup |
| 🎮 Game Updater | Checks and triggers game updates on Steam and Epic Games on demand |
| 📂 File Processor | Read, summarize, and answer questions about local files |
| 💻 Code Helper | Inline code review, debugging, and generation |
| 🌐 Browser Control | Open URLs, navigate tabs, and interact with the browser by voice |
| 📨 Send Message | Compose and send messages through WhatsApp, Telegram, and more |
| 🎬 YouTube Control | Search, play, and control YouTube playback by voice |
| 🖱️ Desktop Control | Taskbar, window management, and desktop-level operations |
| 🧑‍💻 Silent Language Memory | Detects spoken language on first use — all future sessions adapt automatically |
| 📱 Remote Dashboard | Control the assistant from your phone via QR code pairing |
| ⚡ Auto-Start on Boot | Registers with the OS startup system (registry / LaunchAgent / .desktop) |
| 📋 Clipboard Intelligence | Copy any text → floating panel with Translate / Summarise / Explain / Fix |
| 🎨 Assistant Customization | Change the assistant name and your name from the UI — takes effect immediately |

---

## 🆕 What's New in Mark L

### 🗓️ Session Memory — JARVIS Remembers Yesterday
At the end of every session, JARVIS generates a 1-2 sentence summary of what was discussed and saves it to memory. The next morning, it's mentioned naturally in the briefing:
> *"Good morning, sir — it's 09:15. Yesterday you were working on the Mark L background monitoring feature. Fetching today's headlines now."*

The summary is consumed immediately after use — it never repeats in future briefings and adds zero long-term bloat to memory.

### 👁️‍🗨️ Background Monitoring — JARVIS Watches While You're Away
Tell JARVIS to monitor any topic and it checks for new developments once a day using DuckDuckGo news. When a headline changes, it reports back naturally in your language:
> *"Efendim, takip ettiğiniz yapay zeka haberlerinde bir gelişme var: Google yeni bir model duyurdu."*

Fully opt-in — JARVIS monitors nothing without being explicitly asked. Crypto, financial, and trading topics are blocked at the code level regardless of what is requested. Same headline never triggers twice.

### 🔔 Proactive System 2.0 — Context-Aware, Time-Aware, Non-Repetitive
The proactive engine was rebuilt from the ground up. Instead of a generic check-in after 15 minutes of silence, JARVIS now:
- Knows the **time of day** — morning tone differs from evening tone
- Knows your **active projects** from memory and can ask how something is going
- Knows your **monitored topics** and can bring one up naturally
- Knows **what you were just talking about** (last 8 conversation turns)
- **Rotates** between three focus areas so it never opens with the same line twice
- Has a 20-minute cooldown (up from 10) — less intrusive, more meaningful

### 👁️ Instant Vision Acknowledgment — No More Silent Waiting
When you ask JARVIS to look at your screen or camera, it no longer goes silent while processing. It immediately says something natural ("Looking at your screen now, sir" / "Ekrana bakıyorum efendim") while the capture runs. The actual analysis follows as the next response.

### 📰 Parallel News Search — First Result Wins
News queries now run Gemini Grounded Search and DuckDuckGo news simultaneously in two threads. Whichever delivers a valid result first is used; the other is silently discarded. A Gemini 503 error no longer delays results — the DDG fallback is already running in parallel.

---

## 🗺️ Mark Roadmap

| Mark | Focus |
|---|---|
| **XLVIII** | Instant interrupt · parallel news · two-phase briefing · exponential backoff · vision cooldown |
| **XLIX** | Auto-start · clipboard intelligence · assistant customization |
| **L** | Session memory · background monitoring · proactive 2.0 · instant vision · parallel news search |
| **LI+** | Plugin system · email · quiz mode · calorie counter · calendar |

---

## ⚡ Quick Start

```bash
git clone https://github.com/FatihMakes/Mark-L.git
cd Mark-L
pip install -r requirements.txt
python main.py
```

> ⚠️ **Installation Note:** Some OS-specific dependencies are not bundled in `requirements.txt` to keep the repo lightweight. If you hit a `ModuleNotFoundError`, install the missing package with `pip install <module_name>`.

---

## 📋 Requirements

| Requirement | Details |
| --- | --- |
| **OS** | Windows 10/11, macOS, or Linux |
| **Python** | 3.11 or 3.12 |
| **Desktop session** | A real display server/window manager is needed for the PyQt6 HUD, screen capture, browser automation, and desktop controls. |
| **Audio devices** | Microphone and speaker/output device are required for the Gemini Live voice loop. |
| **API Key** | Free Gemini API key stored as `gemini_api_key` in `config/api_keys.json`; `main.py` reads this file before connecting to Gemini Live. |

---

## ⚠️ Known Limitations / Headless Testing

MARK L is primarily a desktop voice assistant, not a pure terminal service. Most runtime features expect:

- A logged-in desktop environment with a display server and window manager. The PyQt6 HUD, screen/webcam capture, browser automation, window management, clipboard panels, and game/app controls are not meaningfully testable in a bare SSH/container session.
- Working local audio input/output devices. The main loop opens microphone input and streams audio to the Gemini Live API; without audio devices it may fail before conversation starts.
- A Gemini API key at `config/api_keys.json` using the shape below before the live assistant can connect:

```json
{
  "gemini_api_key": "YOUR_KEY_HERE"
}
```

For CI or headless Linux, use the integration dry run instead of `python main.py`:

```bash
xvfb-run -a python3 test_integration.py
```

On minimal Debian/Ubuntu runners, install the system pieces first:

```bash
sudo apt-get install -y xvfb python3-tk
python3 -m pip install -r requirements.txt
```

The Windows-only packages in `requirements.txt` are guarded by platform markers and are skipped automatically on Linux/macOS. The dry run replaces the real GUI with `FakeUI`, redirects state/vault writes into a temporary directory, and does not require a microphone, webcam, Claude CLI, or Gemini API call.

Additional audit checks that avoid hardware/API access can be run with:

```bash
python3 -m pytest test_smoke_audit.py
```

---

## 🗂️ Project Structure

Two layers live side by side: the **voice assistant** (`main.py`, `ui.py`,
`actions/`, `core/`) and the **JARVIS OS** agent layer built on top of it
(`orchestrator.py`, `state/`, `vault/`, `.claude/`). `core/jarvis_os_bridge.py`
is the only seam between them — see `specs/JARVIS_OS.md`.

```
Mark L/
│
│  ── Voice assistant (runtime) ──
├── main.py                   # Core loop — Gemini Live session, audio I/O, tool dispatch
├── ui.py                     # PyQt6 HUD — waveform, log panel, interrupt button, camera feed
├── setup.py                  # Dependency installer + first-run configuration wizard
├── test_integration.py       # End-to-end smoke test — startup, orchestrator cycle, voice tools
├── actions/
│   ├── web_search.py         # Gemini + DDG parallel search (news, research, price, compare)
│   ├── screen_processor.py   # Screen capture & webcam vision via Gemini Live
│   ├── background_monitor.py # User-configured topic watching — daily DDG check, no crypto
│   ├── proactive.py          # Proactive 2.0 — time/context/rotation-aware check-ins
│   ├── reminder.py           # OS-native scheduled notifications
│   ├── system_monitor.py     # CPU / RAM / GPU / temperature telemetry
│   ├── computer_settings.py  # Volume, brightness, WiFi, power
│   ├── computer_control.py   # Keyboard shortcuts, mouse, window management
│   ├── open_app.py           # Application launcher
│   ├── browser_control.py    # Web browser control
│   ├── file_controller.py    # File system operations
│   ├── file_processor.py     # Document reading and summarization
│   ├── send_message.py       # Messaging integration
│   ├── weather_report.py     # Live weather data
│   ├── flight_finder.py      # Flight search
│   ├── youtube_video.py      # YouTube playback control
│   ├── game_updater.py       # Game update management (Steam / Epic)
│   ├── code_helper.py        # Code review and generation
│   ├── dev_agent.py          # Developer task agent
│   ├── desktop.py            # Desktop and taskbar control
│   └── github_integration.py # GitHub / LeetCode stats pulls for the Performance team
├── core/
│   ├── prompt.txt            # Assistant personality and tool-routing rules
│   ├── llm_client.py         # Gemini client wrapper (standardized on gemini-3.5-flash)
│   ├── stt.py / tts.py       # Speech-to-text and text-to-speech
│   ├── installer.py          # Runtime dependency checks
│   └── jarvis_os_bridge.py   # ★ The seam: orchestrator ↔ voice app (tools, heartbeat, roll call)
├── memory/
│   ├── memory_manager.py     # Load/save long_term.json — sessions, monitors, identity
│   ├── config_manager.py     # Reads config/api_keys.json
│   └── long_term.json        # Persistent store: identity, preferences, projects, sessions, monitors
├── dashboard/
│   ├── server.py             # FastAPI remote-control server
│   └── static/               # Login + control web UI
├── config/
│   ├── api_keys.json         # 🔒 gitignored — API key, OS setting, assistant name
│   ├── certs/                # 🔒 gitignored — TLS cert + key for the dashboard
│   └── jarvis.ico            # App icon
│
│  ── JARVIS OS agent layer ──
├── orchestrator.py           # Deterministic task engine — dependency graph + Hallucination Loop
├── state/
│   ├── schema.sql            # SQLite task-execution schema (source of truth)
│   ├── verify_task.py        # Default verification — proves an agent wrote a real vault artifact
│   └── orchestrator.db       # 🚫 gitignored — rebuilt from schema.sql on first run
├── .claude/
│   ├── agents/               # 9 supervisor subagent definitions
│   └── skills/               # 28 micro-agent skills, one dir per skill
├── vault/                    # Obsidian knowledge base
│   ├── raw/                  # (scaffolded, not yet populated)
│   ├── wiki/                 # mark_l_memory.md — synced from memory/long_term.json
│   └── outputs/task_summaries/  # One markdown summary per done/blocked task
│
│  ── Documentation ──
├── specs/JARVIS_OS.md        # Architecture spec — §10 tracks what is and isn't built
└── docs/
    ├── 3D_UI_ARCHITECTURE.md # HUD rendering notes
    └── github_screenshot.png
```

---

## ⚠️ License

Personal and non-commercial use only.
Licensed under **[Creative Commons BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**.

---

## 👤 Connect with the Creator

Engineered by a developer building a real-world JARVIS-style assistant.
⭐ **Star the repository to support the journey to Mark 100.**

| Platform | Link |
| --- | --- |
| YouTube | [@FatihMakes](https://www.youtube.com/@FatihMakes) |
| Instagram | [@fatihmakes](https://www.instagram.com/fatihmakes) |
