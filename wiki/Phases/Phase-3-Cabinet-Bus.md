# Phase 3 — Cabinet bus + minimal UI
**Status:** ✅ complete (showable demo; long-running MAME-side plugin deferred)
**Goal:** Stand up the cabinet bus described in
`arcade_cabinet_fault_simulator_plan.md` § "The cabinet bus", and put a
minimal UI on top so a user can pick a fault from the schematic-view UI
and have it actually flip a `FAULT_BUFFER.MODE` parameter inside a
running netlist. End-state: open the UI, click a pin on the sync
generator schematic, watch the simulated VSYNC waveform stop pulsing.
**Estimate:** 4–6 weekends. **Actual: 1 evening.**
## Architectural choice: scenario-per-request, not long-running plugin
The original plan called for a Lua plugin inside MAME that holds a
long-running netlist and accepts `set_fault` / `subscribe_net` over a
TCP socket. That's still the right end state, but it's a lot of MAME
internals work for the first browser demo.
The Phase 3 implementation instead uses a **scenario-per-request**
pattern that gets us the same UX with ~10× less code:
- The Flask cabinet-bus server holds the instrumented netlist as a
  template string.
- Each `POST /api/run` request takes a fault dict, generates a scenario
  `.cpp` by appending `PARAM(FB_*.MODE, ...)` lines, runs `nltool` as a
  subprocess against the scenario, parses the resulting log files, and
  returns the waveforms as JSON.
- The UI fetches the manifest once at boot, draws an SVG schematic with
  one clickable badge per fault target, and refreshes the waveforms on
  every fault toggle.
Deferred to a Phase 3.5 follow-up:
- Long-running MAME-side Lua plugin (`vendor/mame/plugins/cabinet_bus/`).
- WebSocket-based live waveform streaming (vs. one-shot poll).
- Hooking the netlist to MAME's actual centiped driver so faults manifest
  on the game's video output instead of just the standalone netlist.
## What landed
- `tools/cabinet_bus/runner.py` — stateless nltool wrapper. Takes a
  template path + fault dict + duration, returns parsed waveforms. Pure
  enough to unit-test (10/10 tests pass in `test_runner.py`).
- `tools/cabinet_bus/server.py` — Flask app exposing `GET /`,
  `GET /api/manifest`, `POST /api/run`, `GET /static/<file>`. Validates
  fault-device names against the manifest (defends against scenario-
  file injection through the JSON body).
- `tools/cabinet_bus/start.sh` — launcher; activates the venv, starts
  the server on `127.0.0.1:5050`.
- `tools/cabinet_bus/requirements.txt` — just Flask.
- `ui/index.html` + `ui/style.css` + `ui/app.js` — vanilla-JS browser
  UI. SVG block diagram of the sync generator with one clickable badge
  per fault target, sidebar showing currently-active faults, two
  Canvas-based waveform plots (HSYNC_n, VSYNC_n) that step-render the
  parsed log data.
## Demo recipe
```bash
# 1. Make sure the venv exists and Flask is installed.
cd /home/jackie/arcade-sim
source .venv/bin/activate
pip install flask         # if not already done
# 2. Make sure the instrumented netlist + manifest are in place.
ls build/instrumented/sync_generator.cpp \
   build/instrumented/sync_generator.manifest.json
# 3. Start the cabinet bus.
./tools/cabinet_bus/start.sh
# Cabinet bus listening on http://127.0.0.1:5050
# 4. Open the URL in a browser. You should see:
#    - The sync generator block diagram on the left
#    - 8 green badges (the FAULT_BUFFER targets) on key signals
#    - HSYNC_n and VSYNC_n waveforms at the bottom toggling at the
#      expected rates
# 5. Click any green badge → fault-mode dropdown.
#    Pick STUCK_LO on V_LO.QC → the badge turns red, the active-faults
#    sidebar fills, and VSYNC_n freezes high while HSYNC_n keeps
#    pulsing. That's the rolling-picture fault.
# 6. Pick STUCK_HI on H_HI.QD → HSYNC_n behavior changes too (it now
#    asserts more often).
# 7. Click "Reset all faults" to go back to NORMAL.
```
First page load takes ~150 ms (one nltool spawn). Subsequent fault
flips are similar. Plenty fast for an interactive demo.
## Smoke-test verification (no browser needed)
```bash
# Start the server in the background.
./tools/cabinet_bus/start.sh --port 5050 &
sleep 2
# Manifest comes back with 8 entries.
curl -s http://127.0.0.1:5050/api/manifest | python -m json.tool | head
# Healthy run: 98 HSYNC transitions, 9 VSYNC.
curl -s -X POST http://127.0.0.1:5050/api/run \
     -H 'Content-Type: application/json' -d '{"faults": {}}' \
  | python -c 'import sys,json;d=json.load(sys.stdin); print({k: len(v) for k,v in d["waveforms"].items()})'
# Faulted run: 98 HSYNC, 4 VSYNC — VSYNC stuck.
curl -s -X POST http://127.0.0.1:5050/api/run \
     -H 'Content-Type: application/json' -d '{"faults": {"FB_V_LO_QC": 2}}' \
  | python -c 'import sys,json;d=json.load(sys.stdin); print({k: len(v) for k,v in d["waveforms"].items()})'
kill %1
```
## Gotchas
- The Flask dev server is single-threaded, which is fine for one user.
  Don't expose this to the network. The launcher binds 127.0.0.1 only.
- nltool spawns are bounded to 30 seconds with `subprocess.run(...,
  timeout=30)`. Anything longer is treated as a fault in the netlist.
- `--time_to_run` from the request is clamped to `[10µs, 50ms]` so a
  rogue client can't exhaust CPU with a 10-second simulation.
- Fault-device names from the JSON body are validated against the
  manifest before being interpolated into the scenario `.cpp`. This
  prevents trivial `.cpp` / shell injection through the API surface.
## What unblocks Phase 4
- The cabinet bus protocol (`set_fault` via `POST /api/run` with
  `{faults: {...}}`) is established and exercised by a real UI.
- Adding peripheral models is now a matter of extending the request
  schema (`{faults: {...}, peripherals: {...}}`), the manifest format,
  and the UI to render new components. The netlist solver doesn't need
  to know about it.
- Phase 3.5 (long-running MAME plugin) can ride on top of this work
  without re-doing the UI — just swap the Flask `/api/run` handler from
  scenario-per-request to plugin RPC.
## Navigation
← Previous: [Phase 2 — Sync generator](Phase-2-Sync-Generator.md) ·
Next: [Phase 3.5 — MAME bridge](Phase-3.5-MAME-Bridge.md) →
