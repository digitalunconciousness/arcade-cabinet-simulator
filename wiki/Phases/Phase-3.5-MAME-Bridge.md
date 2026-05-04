# Phase 3.5 — MAME bridge
**Status:** ✅ complete
**Goal:** Wire MAME running Centipede into the cabinet bus, so the
browser GUI can talk to a live emulator alongside the existing fault
injection on the standalone netlist. End-state: open the UI, see live
ROM name + frame counter from MAME, click Pause / Resume / Soft reset
and watch the running game respond.
**Estimate:** treated as a small follow-up to Phase 3. **Actual: 1 evening.**
## What landed
- `vendor/mame/plugins/cabinet_bus/init.lua` — Lua plugin running inside
  MAME. Opens a TCP listener on `127.0.0.1:5051`, accepts newline-
  delimited JSON commands, returns JSON-line replies. Hooks
  `add_machine_frame_notifier` for per-machine frame counting and trackball
  delta draining. `add_machine_reset_notifier` resets counters and caches.
  Plugin defaults to `start: false`; must be enabled with `-plugin cabinet_bus`.
  **Digital button API:** `press_button` / `release_button` / `clear_buttons`
  / `list_buttons` — drives `ioport_field:set_value()` each frame so held
  buttons stay held until explicitly released. `held_buttons` and
  `button_field_cache` are cleared on machine reset.
  **Auto-reconnect:** the periodic handler detects ~10 seconds of silence
  after the first client connection and reopens the listener, so Flask can
  reconnect without restarting MAME.
- `vendor/mame/plugins/cabinet_bus/plugin.json` — plugin metadata.
- `patches/0002-Add-cabinet_bus-plugin-socket-bridge-for-the-cabinet.patch` —
  patch series entry so a fresh MAME clone reproduces the plugin.
- `tools/cabinet_bus/mame_client.py` — Python socket client. Holds one
  long-lived TCP connection across calls; auto-reconnects once on broken
  connection. Methods: `press_button()`, `release_button()`,
  `clear_buttons()`, `list_buttons()`.
- `tools/cabinet_bus/server.py` — Flask server `/api/mame/*` endpoints.
  New endpoints: `POST /api/mame/press_button`, `POST /api/mame/release_button`,
  `POST /api/mame/clear_buttons`, `GET /api/mame/list_buttons`. Soft reset
  clears all fault state. PSU watcher does not auto-resume MAME when paused.
- `tools/run-demo.sh` — single-command launcher: Xvfb + MAME + Flask.
  Passes `-skip_gameinfo` so MAME starts straight into gameplay.
- `ui/index.html` + `ui/app.js` + `ui/style.css` — emulator panel with
  live MJPEG video feed, ROM name, frame counter, paused state, and control
  buttons. Keyboard controls: WASD drives the trackball; Space, 1, 2, 5
  press digital buttons. Video stream retries until ffmpeg grab is ready.
## Protocol
Both directions speak newline-terminated JSON objects. One request
yields one reply; replies always include an `ok` boolean.
Commands:
- `{"cmd":"ping"}` → `{"ok":true,"pong":true,"app":"mame","version":"0.287"}`
- `{"cmd":"get_state"}` → `{"ok":true,"rom":"centiped3","paused":false,"frame":12345,...}`
- `{"cmd":"pause"}` → updated state with `paused:true`
- `{"cmd":"resume"}` → updated state with `paused:false`
- `{"cmd":"soft_reset"}` → `{"ok":true,"reset":"soft"}`
- `{"cmd":"trackball_delta","dx":N,"dy":N}` → accumulate per-frame trackball motion
- `{"cmd":"press_button","name":"P1 Button 1"}` → hold a digital input until released
- `{"cmd":"release_button","name":"P1 Button 1"}` → release a held digital input
- `{"cmd":"clear_buttons"}` → release all held buttons
- `{"cmd":"list_buttons"}` → list all ioport field names available in the running ROM
- `{"cmd":"stuck_byte","addr":N,"value":N|null,"cpu":"maincpu"}` → arm/disarm a stuck-at RAM cell
- `{"cmd":"clear_stuck"}` → disarm all stuck cells
- `{"cmd":"set_crt_fault","effect":"...","brightness":0.8}` → set active CRT visual overlay

Unknown commands return `{"ok":false,"error":"..."}`.
## Architectural choice: persistent connection + plugin reconnect
MAME's `emu.file("", 7)` socket abstraction is a one-shot listener:
when the connected client closes its socket, the listener disappears
and a follow-up `connect()` from a fresh client gets ECONNREFUSED.
We handle this at both ends:

**Python side (`MameClient`):** holds one long-lived TCP connection
across all requests. Flask is single-threaded so there's no contention.
Auto-reconnects once on `ConnectionResetError` / `BrokenPipeError`
(handles MAME restart while Flask stays up).

**Lua side (`init.lua` periodic handler):** tracks whether a client
ever sent data (`ever_got_data`). Once a client has connected, if no
bytes arrive for ~10 seconds (~600 frames at 60 Hz), the plugin closes
its stale socket and reopens the listener. This handles the Flask
server restarting while MAME stays up. The 10-second grace period
prevents false reconnects during idle periods.
## Demo recipe
One command:
```bash
source .venv/bin/activate
bash tools/run-demo.sh
# ==> starting virtual display :99 (Xvfb)
# ==> starting MAME (centiped3 with cabinet_bus plugin)
# ==> waiting for cabinet_bus plugin on 127.0.0.1:5051 ... ok
# ==> starting cabinet bus server on http://127.0.0.1:5050
```
Open `http://127.0.0.1:5050`. The MAME panel shows a live MJPEG video
feed plus ROM, frame counter, and paused state. Click **Pause** — the
running Centipede freezes; **Resume** lets it continue; **Soft reset**
restarts the game and clears all injected faults.

Keyboard controls (browser window focused):
- **W / A / S / D** — trackball up/left/down/right
- **Space** — fire
- **1 / 2** — 1-player / 2-player start
- **5** — insert coin

**Note:** MAME must run from `vendor/mame/` to find its plugins.
`run-demo.sh` does this automatically; launching MAME from the repo
root will fail with `Could not load plugin: cabinet_bus`.
## Smoke-test verification (no browser needed)
After both processes are up:
```bash
curl -s http://127.0.0.1:5050/api/mame/state | python -m json.tool
# {"app":"mame","available":true,"frame":<n>,"paused":false,"rom":"centiped3",...}
curl -s -X POST http://127.0.0.1:5050/api/mame/pause | python -m json.tool
# {"available":true,"paused":true,...}
sleep 1
curl -s http://127.0.0.1:5050/api/mame/state | python -m json.tool
# frame counter should NOT advance significantly while paused
curl -s -X POST http://127.0.0.1:5050/api/mame/resume | python -m json.tool
sleep 1
curl -s http://127.0.0.1:5050/api/mame/state | python -m json.tool
# frame counter advances by ~60 (one second @ 60 fps)
curl -s -X POST http://127.0.0.1:5050/api/mame/soft_reset | python -m json.tool
sleep 0.5
curl -s http://127.0.0.1:5050/api/mame/state | python -m json.tool
# frame counter is small (just-restarted)
```
## Gotchas
- The frame counter ticks via `add_machine_frame_notifier`, which fires
  on display updates (~60 Hz when running, also during pause for UI
  redraws). The number isn't a strict CPU-cycle counter, but it's a
  good enough liveness indicator for the UI.
- Pause/resume go through `emu.pause()` / `emu.unpause()` rather than
  `machine:pause()` — the methods are bound on the `emu` module, not
  on the machine object. Using `manager.machine:pause()` will fail
  with "attempt to call a nil value (method 'pause')".
- The plugin's `start: false` flag means it doesn't autoload; you must
  pass `-plugin cabinet_bus` explicitly. Intentional — we don't want
  every MAME launch to bind 5051.
- If the Flask process restarts while MAME keeps running, the
  `MameClient`'s persistent connection is lost and reconnect happens
  automatically on the next request. If MAME restarts while Flask
  keeps running, the same auto-reconnect handles it.
## What's still deferred (future Phase 3.5+)
- Live waveform streaming via WebSocket. Current UI polls `/api/run`
  on each fault toggle; per-frame streaming would feel more like an
  oscilloscope.
- Hooking the netlist into MAME's centiped driver so faults manifest
  on the actual game's video output. Centipede doesn't use the
  netlist solver in MAME, so this requires migrating Centipede's
  sync generator from C++ functional emulation to a netlist machine
  — large piece of work, deferred to Phase 5+.
- Watching arbitrary memory addresses or netlist nets through the same
  bridge. The protocol can extend by adding new `cmd` values; UI
  consumers do the right thing.
## What unblocks Phase 4
- The cabinet bus now speaks to both the standalone netlist (via
  `/api/run`) and the live emulator (via `/api/mame/*`). Phase 4
  peripheral models slot in with a third surface (`/api/peripherals/*`)
  using the same JSON-over-HTTP pattern.
## Navigation
← Previous: [Phase 3 — Cabinet bus + UI](Phase-3-Cabinet-Bus.md) ·
Next: [Phase 4 — PSU + peripherals](Phase-4-PSU-Peripherals.md) →
