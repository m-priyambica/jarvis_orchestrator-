# 3D Holographic UI — Architecture Plan

Goal: replace the PyQt6 HUD (`ui.py`) with a React Three Fiber (R3F) frontend
that renders an Iron Man–style WebGL HUD, driven by the existing Python
orchestrator — without rewriting the orchestrator itself.

## Status

- **Step 1 (broadcast) — done.** `main.py`'s `_render_jarvis_os_panel()`
  pushes `{"type": "agent_roll_call", agents, tasks}` over the existing
  `/ws` every panel refresh (~10s). Each agent carries
  `current_file_reference`.
- **Step 2 (R3F frontend) — Phase 1 done.** Scaffolded in
  `dashboard/frontend/`, builds clean, renders the core + a live 9-agent
  ring, and logs each roll call to the browser console.
- **Steps 3–4 (serve the build, retire PyQt) — not started.** The frontend
  still runs on Vite's dev server; `dashboard/server.py` still serves
  `dashboard/static/app.html`.

### Running Phase 1

```bash
# terminal 1 — the backend (this also starts the dashboard on :8000)
python main.py

# terminal 2 — the HUD
cd dashboard/frontend
npm run dev            # http://localhost:5173
```

The WebSocket needs the same auth token the existing dashboard uses. Log in
once at `http://localhost:8000/login` (that stores `jarvis_token` in
`sessionStorage`), or append `?token=<token>` to the Vite URL. Without one
the HUD shows `UNAUTHORIZED` and explains itself in the console; a rejected
token closes with code 4001 and is not retried.

## You already have most of the backend

`dashboard/server.py` is already a FastAPI app with:
- token-based auth (`/login`, `/api/device-login`) + AES-256-CBC payload
  encryption keyed off the session key
- a broadcast-capable WebSocket at `/ws` (`ConnectionManager.broadcast`,
  `_clients: set[WebSocket]`, 300-message `_history` replay buffer)
- a command queue (`_command_queue`) that feeds text commands back into
  `main.py`
- static file serving (`dashboard/static/app.html`, `login.html`)

This is the backend the WebGL HUD needs. **Don't stand up a second FastAPI
app** — extend this one. The only new backend work is (a) broadcasting richer
state than it does today, and (b) serving a React build instead of
`app.html`.

## Step 1 — Broaden what `/ws` broadcasts

Today `broadcast()` is called with ad-hoc chat/status messages. Add a
typed envelope so the 3D frontend can render distinct HUD elements:

```python
await manager.broadcast({
    "type": "orchestrator_state",   # | "agent_roll_call" | "voice_level" | "assistant_text"
    "payload": {...},
})
```

Sources to wire in on the Python side:
- `core/jarvis_os_bridge.py` — `get_agent_roll_call()` already produces
  structured per-agent status; broadcast it on change instead of (or in
  addition to) formatting it for the PyQt HUD panel.
- `orchestrator.py` — task state transitions from `state/schema.sql`
  (`execution_logs`, `done`/`running`/`failed`) become HUD "system nodes."
- `main.py`'s `_send_realtime`/`_listen_audio` loop — push a coarse
  volume/activity level (not raw PCM) for the mic-reactive HUD ring, e.g.
  every ~50ms from the existing `callback()` in `_listen_audio`.

Keep payloads small and pre-aggregated; the frontend should never need to
poll SQLite directly.

## Step 2 — React Three Fiber frontend

New directory, e.g. `dashboard/frontend/` (Vite + React + TypeScript):

```
dashboard/frontend/
  src/
    App.tsx              # [built] WS wiring, console logging, HTML overlays
    hud/
      HologramShell.tsx  # [built] R3F <Canvas>, camera rig, bloom postprocessing
      ArcReactorCore.tsx # [built] central rotating core; `activity` prop is the
                         #         seam where "voice_level" will plug in
      AgentRing.tsx      # [built] orbiting nodes for the 9 agents, colored by status
      TaskStream.tsx     # [todo]  scrolling HUD text panel for execution_logs
    lib/
      ws.ts              # [built] typed message dispatch + token/4001 handling
  vite.config.ts         # [built] proxies /ws + /api to :8000
  package.json
```

Note on `ws.ts`: it does **not** implement the CryptoJS/AES decrypt that
`app.html` uses. That scheme only wraps the `command` text channel (the
`enc` field on outbound commands); the `agent_roll_call` telemetry this HUD
consumes is sent as plain JSON by `broadcast()`, so only the bearer token
is needed. Decrypt only becomes necessary if the HUD grows a command input.

Key libraries: `@react-three/fiber`, `@react-three/drei` (rings, text,
glow helpers), `@react-three/postprocessing` (bloom for the "hologram"
glow look), `three`.

The WS client reuses the **same auth/encryption flow** already implemented
in `dashboard/static/app.html` — same token query param, same AES-CBC
decrypt — so the login page and pairing flow don't change at all, only what
renders after login.

## Step 3 — Serve the build through the existing server

Two options, pick based on how much you want dev-mode hot reload:

- **Simple (recommended first)**: `npm run build` → outputs to
  `dashboard/frontend/dist/`. Point `_build_app()`'s static mount /
  `_app_html` loader at the built `index.html` instead of
  `dashboard/static/app.html`. One process, one port (8000), no CORS.
- **Dev mode**: run Vite's dev server on a separate port (5173) with
  `server: { proxy: { '/ws': 'ws://localhost:8000' } }` in
  `vite.config.ts` while iterating on the HUD visuals, then switch to the
  built-output mount for anything demoed or shipped.

## Step 4 — Decommission PyQt6 HUD incrementally

`ui.py` (`JarvisUI`, `_render_jarvis_os_panel`, the desktop-shortcut
creator, Quick Drawer) keeps working during the transition — don't delete
it in the same pass. Suggested order:
1. Ship the R3F dashboard alongside the PyQt HUD (both consume the same
   backend state).
2. Once the roll call, task stream, and voice-reactive core are at parity
   with what `_render_jarvis_os_panel` shows today, make the browser
   dashboard the default entry point.
3. Only then trim `ui.py` down to whatever still needs a native window
   (e.g. the desktop-shortcut creator, if that stays OS-level).

## Explicitly out of scope here

- Rewriting `orchestrator.py`'s task engine — it stays deterministic
  Python/SQLite; the 3D UI is a new *consumer* of its state, not a
  replacement for it.
- Changing the Gemini Live API audio pipeline (`_send_realtime`,
  `_listen_audio` in `main.py`) beyond the volume-level tap described in
  Step 1.
