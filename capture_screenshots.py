#!/usr/bin/env python3
"""Capture real rendered screenshots of the JARVIS Qt UI.

Run with a display server, for example:

    xvfb-run -a python3 capture_screenshots.py

The script instantiates the real ui.JarvisUI/MainWindow widgets and uses Qt's
QWidget.grab() path. It does not connect to Gemini, open audio devices, start a
camera, or call the Claude CLI. The agent data shown in the roll-call capture is
mock data injected through the real set_roll_call()/show_content() UI methods.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Prefer an existing Xvfb/desktop display. If none is present, use Qt's
# offscreen platform so the same real widgets can still render in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen" if not os.environ.get("DISPLAY") else "xcb")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication

import ui as jarvis_ui
from core.jarvis_os_bridge import format_roll_call_for_speech

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "docs" / "screenshots"

MOCK_ROSTER = [
    {
        "id": "synthesizer", "name": "Synthesizer", "status": "idle",
        "current_file_reference": "vault/wiki/README.md",
        "last_task": {"title": "Summarize memory updates", "status": "done"},
    },
    {
        "id": "orchestrator", "name": "Orchestrator", "status": "idle",
        "current_file_reference": "state/orchestrator.db", "last_task": None,
    },
    {
        "id": "mentor", "name": "Mentor", "status": "running",
        "current_file_reference": "vault/wiki/leetcode-dsa-plan.md",
        "last_task": {"title": "Prepare DSA study session", "status": "running"},
    },
    {
        "id": "architect", "name": "Architect", "status": "idle",
        "current_file_reference": "orchestrator.py",
        "last_task": {"title": "Review orchestrator invariants", "status": "done"},
    },
    {
        "id": "scout", "name": "Scout", "status": "running",
        "current_file_reference": "https://example.com/jobs",
        "last_task": {"title": "Find new internship leads", "status": "running"},
    },
    {
        "id": "brand", "name": "Brand", "status": "idle",
        "current_file_reference": "vault/outputs/README.md", "last_task": None,
    },
    {
        "id": "interrogator", "name": "Interrogator", "status": "blocked",
        "current_file_reference": "vault/outputs/task_summaries/mock.md",
        "last_task": {"title": "Run mock behavioral interview", "status": "blocked"},
    },
    {
        "id": "performance", "name": "Performance", "status": "idle",
        "current_file_reference": "", "last_task": None,
    },
    {
        "id": "radar", "name": "Radar", "status": "idle",
        "current_file_reference": "vault/raw/README.md",
        "last_task": {"title": "Scan AI infrastructure news", "status": "done"},
    },
]


def _process(app, seconds: float = 0.8) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)


def _save_widget(widget, path: Path) -> None:
    pixmap = widget.grab()
    if pixmap.isNull():
        screen = QGuiApplication.primaryScreen()
        pixmap = screen.grabWindow(widget.winId()) if screen else pixmap
    if pixmap.isNull() or not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"failed to save screenshot: {path}")
    print(f"saved {path.relative_to(ROOT)}")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="jarvis_ui_capture_") as tmp:
        # Avoid the first-run setup overlay without touching the user's real
        # config/api_keys.json. This is a dummy value solely to render the real
        # startup HUD in a screenshot; no Gemini connection is made.
        cfg = Path(tmp) / "api_keys.json"
        cfg.write_text(json.dumps({"gemini_api_key": "DUMMY_SCREENSHOT_KEY", "os_system": "linux"}), encoding="utf-8")
        jarvis_ui.API_FILE = cfg
        jarvis_ui.CONFIG_DIR = cfg.parent

        app = jarvis_ui.QApplication.instance() or jarvis_ui.QApplication(sys.argv)
        app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True)
        ui = jarvis_ui.JarvisUI(str(ROOT / "face.png"))
        win = ui._win
        win.resize(980, 700)
        win.show()
        _process(app, 1.2)

        ui.write_log("SYS: JARVIS OS screenshot capture started.")
        ui.set_state("LISTENING")
        _process(app, 0.6)
        _save_widget(win, OUT_DIR / "hud_startup.png")

        panel_text = "AVENGERS ASSEMBLE — JARVIS OS ROLL CALL\n\n" + format_roll_call_for_speech(MOCK_ROSTER)
        ui.set_roll_call(MOCK_ROSTER)
        ui.show_content("JARVIS OS Roll Call", panel_text)
        ui.write_log("JARVIS OS: mock roll-call data injected for screenshot capture.")
        _process(app, 1.2)
        _save_widget(win, OUT_DIR / "agent_rollcall.png")

        win.close()
        _process(app, 0.2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
