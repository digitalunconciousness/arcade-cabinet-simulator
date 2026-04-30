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
  `add_machine_frame_notifier` to track a per-machine frame counter
  and `add_machine_reset_notifier` to reset it on hard/soft reset.
  Plugin defaults to `start: false` so it has no effect unless
  explicitly enabled with `-plugin cabinet_bus`.
- `vendor/mame/plugins/cabinet_bus/plugin.json` — plugin metadata.
- `patches/0002-Add-cabinet_bus-plugin-socket-bridge-for-the-cabinet.patch` —
  patch series entry so a fresh MAME clone reproduces the plugin.
- `tools/cabinet_bus/mame_client.py` — Python socket client. Holds one
  long-lived TCP connection across calls (MAME's `emu.file` socket
  abstraction only listens for one connection at a time, so closing the
  socket after each request would lose the listener); auto-reconnects
  once on broken connection.
- `tools/cabinet_bus/server.py` — Flask server gains the `/api/mame/*`
  endpoints proxying to the plugin. They return HTTP 503 with
  `{"available": false}` when MAME isn't running, so the UI can hide
  the panel gracefully.
- `ui/index.html` + `ui/app.js` + `ui/style.css` — adds a "Centipede
  emulator (MAME)" panel above the schematic with ROM, paused-state,
  frame counter, and build version, plus Pause / Resume / Soft-reset
  buttons. Polls `/api/mame/state` every 1 second; switches between the
  live panel and an offline placeholder card based on whether the
  bridge is reachable.
## Protocol
Both directions speak newline-terminated JSON objects. One request
yields one reply; replies always include an `ok` boolean.
Commands:
- `{"cmd":"ping"}` → `{"ok":true,"pong":true,"app":"mame","version":"0.287"}`
- `{"cmd":"get_state"}` → `{"ok":true,"rom":"centiped3","paused":false,"frame":12345,"app":"mame","version":"0.287"}`
- `{"cmd":"pause"}` → updated state with `paused:true`
- `{"cmd":"resume"}` → updated state with `paused:false`
- `{"cmd":"soft_reset"}` → `{"ok":true,"reset":"soft"}`
Unknown commands return `{"ok":false,"error":"..."}`.
## Architectural choice: persistent connection
MAME's `emu.file("", 7)` socket abstraction is a one-shot listener:
when the connected client closes its socket, the listener disappears
and a follow-up `connect()` from a fresh client gets ECONNREFUSED.
Two ways around it:
1. Have the Lua plugin re-open the listener when the connection drops.
   `emu.file` doesn't expose a clean way to detect EOF, so this
   requires polling or guessing.
2. Keep one long-lived TCP connection from Flask and reuse it across
   requests.
Option 2 is the simpler/correct fix and is what we ship. Flask is
single-threaded by default so there's no contention. `MameClient`
auto-reconnects once if the connection breaks (MAME exiting, plugin
restart, etc.).
## Demo recipe
Two terminals.
**Terminal 1 — MAME with the cabinet_bus plugin:**
```bash
cd /home/jackie/arcade-sim/vendor/mame
./mame -plugin cabinet_bus \
    -rompath /home/jackie/arcade-sim/roms \
    -window -sound pipewire centiped3
# stderr should show: cabinet_bus: listening on socket.127.0.0.1:5051
```
**Terminal 2 — Flask cabinet bus + UI:**
```bash
cd /home/jackie/arcade-sim
./tools/cabinet_bus/start.sh
# Cabinet bus listening on http://127.0.0.1:5050
```
Open `http://127.0.0.1:5050` in a browser. The "Centipede emulator
(MAME)" panel auto-activates once it detects the plugin. Click
**Pause** — the running Centipede freezes mid-frame; **Resume** lets
it continue; **Soft reset** restarts the game and the frame counter
resets to 0.
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
