#!/usr/bin/env python3
"""Integration dry-run for the JARVIS OS <-> Mark-L wiring in main.py.

Exercises, end to end, exactly the code this integration added to
JarvisLive: _init_jarvis_os() (startup), _render_jarvis_os_panel() (HUD /
content panel), one full pass of _run_jarvis_os_orchestrator()'s body
(vault sync + orchestrator drain + panel refresh + narration gate), the
real _run_jarvis_os_orchestrator() coroutine itself (fast-forwarded a few
iterations), and every 'jarvis_os' voice-tool action dispatched through
_execute_tool() — the same function a real Gemini tool call would hit.

Why the stubbing: main.py pulls in a voice/vision/GUI assistant's worth of
dependencies (PyQt6, sounddevice, psutil, playwright, ...) that have
nothing to do with this integration. Rather than requiring a full install
just to run this check, missing ones are stubbed with MagicMock, and
ui.JarvisUI is always replaced with a lightweight FakeUI (never a real Qt
window, regardless of whether PyQt6 happens to be installed) — then this
harness drives the specific methods directly instead of calling the real
run() (which would try to open a mic stream and connect to the live Gemini
API, neither available or wanted here).

Every DB/vault path is redirected into a throwaway temp directory for the
duration of the run — this script never touches the real
state/orchestrator.db or vault/.

Usage:
    python test_integration.py

Exit code 0 and "ALL CHECKS PASSED" means zero runtime exceptions across
every exercised path. Any exception aborts immediately with a traceback and
exit code 1.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import traceback
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# main.py's tool dispatch prints emoji (e.g. "[JARVIS] 🔧 ..."). On Windows,
# stdout defaults to the legacy console codepage (cp1252), which can't
# encode them and raises UnicodeEncodeError — a console configuration
# issue, not a bug in the code under test. Force UTF-8 so this harness
# behaves the same regardless of the host console's codepage.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


# ── Stubbing: install fakes for what main.py needs but this box may lack ───

class FakeUI:
    """Stands in for ui.JarvisUI: the same thread-safe surface JarvisLive
    calls (write_log, show_content, set_state, the on_* setters) with no
    real Qt window behind it. Records everything so the test can assert on
    what actually got rendered.
    """

    def __init__(self):
        self.logs: list[str] = []
        self.panels: list[tuple[str, str]] = []
        self.states: list[str] = []
        self.muted = False
        self.current_file = None
        self.on_text_command = None
        self.on_remote_clicked = None
        self.on_interrupt = None

    def write_log(self, text: str) -> None:
        self.logs.append(text)

    def show_content(self, title: str, text: str) -> None:
        self.panels.append((title[:48], text[:4000]))

    def set_state(self, state: str) -> None:
        self.states.append(state)

    def start_camera_stream(self) -> None:
        pass

    def stop_camera_stream(self) -> None:
        pass


def _stub_if_missing(name: str) -> bool:
    """Install a MagicMock at sys.modules[name] only if the real import
    fails. Returns True if a stub was installed, False if the real module
    is already there (in which case it's used as-is — more faithful).
    """
    if name in sys.modules:
        return False
    try:
        __import__(name)
        return False
    except Exception:
        sys.modules[name] = MagicMock(name=f"stub:{name}")
        return True


def install_stubs() -> None:
    # ui.py is always replaced, never conditionally: even if PyQt6 were
    # installed we still don't want a real GUI window opening in a test.
    fake_ui_module = ModuleType("ui")
    fake_ui_module.JarvisUI = FakeUI
    sys.modules["ui"] = fake_ui_module

    # Everything else: only stub what's genuinely missing on this box, so
    # the test uses real behavior wherever it's available (e.g. sounddevice
    # and google.genai are actually installed in this sandbox — no need to
    # fake those; only the hard requirements main.py can't get past without
    # get stubbed).
    for name in ("psutil", "playwright", "playwright.async_api", "sounddevice"):
        stubbed = _stub_if_missing(name)
        print(f"  [stub] {name}: {'mocked (not installed here)' if stubbed else 'using real module'}")


# ── The dry run ──────────────────────────────────────────────────────────

async def dry_run() -> None:
    install_stubs()

    import main  # noqa: E402  (must happen after stubs are installed)
    import orchestrator as orch
    import core.jarvis_os_bridge as bridge

    with tempfile.TemporaryDirectory(prefix="jarvis_os_integration_test_") as tmp:
        tmp_path = Path(tmp)

        # Redirect every path the bridge/orchestrator touch into the scratch
        # dir — this test must never write into the real repo's state/ or
        # vault/.
        orch.DEFAULT_DB_PATH      = tmp_path / "state" / "orchestrator.db"
        bridge.VAULT_DIR          = tmp_path / "vault"
        bridge.BRIEFINGS_DIR      = bridge.VAULT_DIR / "outputs" / "briefings"
        bridge.TASK_SUMMARIES_DIR = bridge.VAULT_DIR / "outputs" / "task_summaries"
        bridge.WIKI_DIR           = bridge.VAULT_DIR / "wiki"

        fake_ui = FakeUI()
        jarvis = main.JarvisLive(fake_ui)
        print("[1/5] JarvisLive constructed with FakeUI — OK")

        # ── Phase 1: startup sequence (what run() calls first) ──────────
        await jarvis._init_jarvis_os()
        assert orch.DEFAULT_DB_PATH.exists(), "startup did not create state/orchestrator.db"
        assert any("JARVIS OS database ready" in l for l in fake_ui.logs), "no startup log line"
        assert fake_ui.panels, "startup did not render the content panel"
        assert "no tasks scheduled yet" in fake_ui.panels[-1][1], "fresh DB should show an empty board"
        print("[2/5] _init_jarvis_os() — DB created, HUD log + content panel rendered — OK")

        # ── Phase 2: seed real work, run one orchestrator cycle exactly
        #     like the background loop's body does (sync -> drain -> render) ──
        conn = orch.connect(orch.DEFAULT_DB_PATH)
        conn.execute(
            "INSERT INTO tasks (id, title, command, assigned_agent_id, max_retries) VALUES (?,?,?,?,?)",
            ("IT-PASS", "dry-run task that passes", 'python -c "exit(0)"', "architect", 3),
        )
        conn.execute(
            "INSERT INTO tasks (id, title, command, assigned_agent_id, max_retries) VALUES (?,?,?,?,?)",
            ("IT-FAIL", "dry-run task that fails", 'python -c "exit(1)"', "architect", 1),
        )
        conn.commit()
        conn.close()

        await asyncio.to_thread(bridge.sync_memory_to_vault)
        summary = await asyncio.to_thread(bridge.run_orchestrator_cycle)
        await jarvis._render_jarvis_os_panel()

        assert len(summary["done"]) == 1 and summary["done"][0]["id"] == "IT-PASS", summary
        assert len(summary["blocked"]) == 1 and summary["blocked"][0]["id"] == "IT-FAIL", summary
        assert (bridge.TASK_SUMMARIES_DIR / "IT-PASS.md").exists(), "no markdown summary for the passing task"
        assert (bridge.TASK_SUMMARIES_DIR / "IT-FAIL.md").exists(), "no markdown summary for the blocked task"
        assert (bridge.WIKI_DIR / "mark_l_memory.md").exists(), "vault sync did not write mark_l_memory.md"
        assert "1 done" in fake_ui.panels[-1][1] and "1 blocked" in fake_ui.panels[-1][1]
        print("[3/5] one orchestrator cycle (sync + drain + render) — task summaries + vault sync + live panel — OK")

        # ── Phase 3: the real background-loop coroutine, fast-forwarded ──
        # _run_jarvis_os_orchestrator() sleeps 600s then loops with 1800s
        # between cycles — patch asyncio.sleep to a near-instant yield so a
        # few real iterations execute, then cancel it (expected, since it's
        # an infinite loop by design) and confirm nothing but the deliberate
        # cancellation was raised.
        real_sleep = asyncio.sleep

        async def fast_sleep(_seconds):
            await real_sleep(0)

        with patch("asyncio.sleep", fast_sleep):
            loop_task = asyncio.create_task(jarvis._run_jarvis_os_orchestrator())
            await real_sleep(0.2)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass  # expected — we deliberately stopped an intentionally infinite loop
        print("[4/5] _run_jarvis_os_orchestrator() ran several fast-forwarded iterations — OK")

        # ── Phase 4: the 'jarvis_os' voice tool, exactly as Gemini would
        #     invoke it through _execute_tool() ──
        for action in ("status", "sync_vault", "briefing", "run"):
            fc = SimpleNamespace(id=f"test-{action}", name="jarvis_os", args={"action": action})
            fr = await jarvis._execute_tool(fc)
            assert fr is not None, f"jarvis_os action '{action}' returned nothing"
        print("[5/5] jarvis_os voice tool — status/sync_vault/briefing/run all dispatched cleanly — OK")


def main_entry() -> int:
    print("Running JARVIS OS <-> Mark-L integration dry-run...\n")
    try:
        asyncio.run(dry_run())
    except Exception:
        print("\n--- FAILED: an exception escaped the dry-run ---")
        traceback.print_exc()
        return 1

    print("\nALL CHECKS PASSED — zero runtime exceptions across startup, one orchestrator "
          "cycle, the live background loop, and every jarvis_os voice action.")
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())
