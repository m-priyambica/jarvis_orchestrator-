#!/usr/bin/env python3
"""Headless smoke/audit checks for JARVIS OS demo readiness.

These tests avoid real microphones, webcams, browser automation, API keys, and
Claude CLI calls. They catch import-time breakage and verify the documented
nine-agent roster stays consistent across agent docs, skill folders, and the
voice tool schema.
"""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent
EXPECTED_AGENTS = {
    "synthesizer", "orchestrator", "mentor", "architect", "scout",
    "brand", "interrogator", "performance", "radar",
}


def _install_headless_stubs() -> None:
    """Stub GUI/hardware-heavy modules only for import smoke tests."""
    sys.modules.setdefault("pyautogui", MagicMock(name="stub:pyautogui"))
    sys.modules.setdefault("pygetwindow", MagicMock(name="stub:pygetwindow"))
    sys.modules.setdefault("sounddevice", MagicMock(name="stub:sounddevice"))
    sys.modules.setdefault("mss", MagicMock(name="stub:mss"))
    sys.modules.setdefault("cv2", MagicMock(name="stub:cv2"))
    sys.modules.setdefault("playwright", MagicMock(name="stub:playwright"))
    sys.modules.setdefault("playwright.async_api", MagicMock(name="stub:playwright.async_api"))

    fake_ui = ModuleType("ui")
    class FakeJarvisUI:  # noqa: D401 - intentionally tiny test double
        """Minimal ui.JarvisUI stand-in for importing main.py."""
        pass
    fake_ui.JarvisUI = FakeJarvisUI
    sys.modules.setdefault("ui", fake_ui)


def _literal_tool_declarations() -> list[dict]:
    """Parse main.py without importing it and return TOOL_DECLARATIONS."""
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TOOL_DECLARATIONS":
                    return ast.literal_eval(node.value)
    raise AssertionError("main.py does not define TOOL_DECLARATIONS")


def test_fake_ui_matches_roll_call_surface() -> None:
    import test_integration
    ui = test_integration.FakeUI()
    roster = [{"id": "mentor", "status": "idle"}]
    ui.set_roll_call(roster)
    assert ui.roll_calls[-1] == roster


def test_headless_imports_core_actions_dashboard() -> None:
    _install_headless_stubs()
    modules = [
        "orchestrator", "core.jarvis_os_bridge", "dashboard.server", "main",
        *[f"actions.{p.stem}" for p in sorted((ROOT / "actions").glob("*.py"))],
    ]
    failures: dict[str, str] = {}
    for module_name in modules:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - reported in assertion
            failures[module_name] = f"{type(exc).__name__}: {exc}"
    assert not failures, failures


def test_reminder_scheduler_failures_are_non_fatal() -> None:
    from actions import reminder as reminder_module

    future = {"date": "2999-01-01", "time": "09:00", "message": "audit"}
    with patch.object(reminder_module, "_get_os", return_value="linux"), \
         patch.object(reminder_module.shutil, "which", return_value=None):
        assert "couldn't register" in reminder_module.reminder(future).lower()

    with patch.object(reminder_module, "_get_os", return_value="windows"), \
         patch.object(reminder_module, "_schedule_windows", return_value=""):
        assert "couldn't register" in reminder_module.reminder(future).lower()

    with patch.object(reminder_module, "_get_os", return_value="mac"), \
         patch.object(reminder_module, "_schedule_mac", return_value=""):
        assert "couldn't register" in reminder_module.reminder(future).lower()


def test_agent_docs_skills_voice_tool_roster_consistent() -> None:
    agent_docs = {p.stem for p in (ROOT / ".claude" / "agents").glob("*.md")}
    skill_prefixes = {p.name.split("-", 1)[0] for p in (ROOT / ".claude" / "skills").iterdir() if p.is_dir()}

    import core.jarvis_os_bridge as bridge
    tool_agents: set[str] = set()
    for decl in _literal_tool_declarations():
        if decl["name"] in {"jarvis_os", "patch_agent"}:
            desc = decl["parameters"]["properties"]["agent"]["description"]
            tool_agents |= {agent for agent in EXPECTED_AGENTS if agent in desc}

    assert set(bridge.AGENT_IDS) == EXPECTED_AGENTS
    assert agent_docs == EXPECTED_AGENTS
    assert skill_prefixes == EXPECTED_AGENTS
    assert tool_agents == EXPECTED_AGENTS
