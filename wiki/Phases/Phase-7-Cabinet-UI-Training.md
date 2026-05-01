# Phase 7 — Complete vertical-slice demo
**Status:** ⏳ planned
**Goal:** A working prototype you can hand to someone unfamiliar with
the project. Centipede runs in MAME; you pick a fault from a named
scenario list; the effect is immediately visible (or audible, or tactile
through the trackball) *in the running emulation*. Every subsystem
wired in Phases 0–6 is now exercised end-to-end in one launch.

This replaces the original "cabinet UI + training mode" scope for Phase
7. The full training-mode polish (KiCad SVG schematic, PCB-photo map,
probe view, scoring) moves to Phase 8.

---

## The vertical-slice contract

After Phase 7, a visitor can:

1. Run `tools/run-demo.sh` — MAME starts Centipede, the Flask server
   starts, the browser opens at `http://localhost:5050`.
2. Choose a named fault scenario from the browser UI dropdown.
3. Click **Apply**. Within one second, the fault takes effect in the
   running game. No restarting MAME.
4. See/hear/feel the change immediately:
   - CRT fault → MAME framebuffer is overlaid by the matching BGFX
     shader effect (collapse, ghosting, dim, etc.).
   - PSU fault → dimmed picture *and* trackball sluggish *and* CPU
     bus errors (sagging 5 V rail couples into all subsystems).
   - RAM fault → corrupted tiles / sprite garbage via stuck-byte injection.
   - Address-decoder fault → missing sprite layer or ROM read errors.
   - Trackball fault → dead axis, reversed axis, or sluggish response
     that the player can feel while trying to aim.
   - Audio fault → POKEY output filtered through WebAudio fault chain
     in the browser (hum, distortion, silence).
5. Click **Clear** to restore normal operation without restarting.

---

## Sub-tasks

### 7.1 — BGFX CRT shader integration

The Phase 6 GLSL shaders (`ui/shaders/crt_*.glsl`) are reference
previews only. Phase 7 wires them into MAME's live output.

**Approach — BGFX screen-chain JSON:**
- Write `vendor/mame/bgfx/chains/cabinet_fault.json` — a BGFX chain
  that reads a `uniform vec2 u_fault` injected via the Lua plugin and
  selects the matching visual transform.
- The Lua plugin receives a `{"cmd":"set_crt_fault","effect":"...","brightness":0.8}`
  command and writes the uniform into BGFX via
  `manager.machine:render():first_target():effect()` (or the BGFX
  uniform API exposed in MAME 0.287 Lua).
- Fallback path: if BGFX uniform injection proves unavailable in
  0.287's Lua surface, use a **screenshot-overlay** approach: the
  Flask server periodically grabs a MAME screenshot via
  `manager.machine:render()`, applies the OpenCV/Pillow filter
  server-side, and serves it as the CRT preview. This is still
  compelling for a demo even if it is not full-frame-rate.
- Shaders needed: normal, no_hv, vertical_collapse, horizontal_collapse,
  weak_focus, brightness_drift, dim_picture, sync_lock_failure,
  ringing_ghosting. (9 effects — all already written in GLSL.)

**New files:**
- `vendor/mame/bgfx/chains/cabinet_fault.json`
- `vendor/mame/bgfx/effects/cabinet_fault_crt.bgfx`
- `tools/cabinet_bus/server.py` — new `POST /api/crt/apply` that
  forwards the Lua `set_crt_fault` command.

---

### 7.2 — PSU fault propagation into MAME

The PSU model (`tools/peripherals/psu.py`) already tracks sagging 5 V
rail and exposes `state()["rails"]["5V"]`. Phase 7 makes every
downstream subsystem *respond* to it inside the running emulation.

**Wiring:**
- **CRT dimming**: already implemented in `crt.py`
  (`_psu_5v_scale()`). Phase 7 propagates the computed
  `effective_brightness` to BGFX via `set_crt_fault`.
- **CPU clock stretch**: a sagging 5 V rail causes marginal logic
  timing. Model this as a `stuck_byte` on a random address picked from
  the Centipede RAM map when `5V < 4.7` — i.e. the PSU fault can now
  spawn transient RAM errors that show up as sprite corruption.
- **Trackball sensitivity**: already wired — trackball Python model
  reads PSU state and adjusts `_effective_sensitivity`. The Lua plugin
  uses this because the Python trackball model scales the dx/dy
  before `POST /api/trackball/motion` reaches MAME.

No new files; changes are in `server.py` (a periodic PSU-status push
loop) and `vendor/mame/plugins/cabinet_bus/init.lua`.

---

### 7.3 — Scenario library

A JSON file per scenario in `tests/scenarios/`. The runner loads them
into the browser UI dropdown.

**Schema (`tests/scenarios/<id>.json`):**
```json
{
  "id": "dim-psu-5v",
  "title": "Dim picture, sluggish controls",
  "difficulty": 1,
  "subsystems": ["PSU", "CRT", "Trackball"],
  "backstory": "Operator reports the picture looks washed out and the trackball feels heavy.",
  "faults": [
    {"type": "peripheral", "target": "PSU1",  "fault": "low_5v"},
    {"type": "peripheral", "target": "CRT1",  "fault": "dim_picture"},
    {"type": "peripheral", "target": "TRACK1","fault": "dirty_roller"}
  ],
  "visible_effect": "BGFX brightness_drift + reduced trackball dx/dy in-game",
  "diagnosis_hint": "Measure 5 V rail at J1 pin 4 with a DMM."
}
```

**Initial 12 scenarios to author:**

| # | ID | Subsystems | Visible effect |
|---|-----|-----------|---------------|
| 1 | dim-psu-5v | PSU, CRT, Trackball | Dim picture + heavy controls |
| 2 | vertical-collapse | CRT | Screen collapses to horizontal bar |
| 3 | dead-trackball-x | Trackball | Can't steer left/right |
| 4 | reversed-trackball | Trackball | Controls inverted |
| 5 | sprite-ram-glitch | RAM | Tile corruption mid-screen |
| 6 | address-decoder-rom | AddrDecoder | ROM bank missing (frozen game) |
| 7 | hum-amp | Audio | 60 Hz hum over POKEY output |
| 8 | dead-amp | Audio | Silence |
| 9 | sync-lock | CRT | Rolling picture / picture tears |
| 10 | ringing-ghosting | CRT | Fuzzy double-image on sprites |
| 11 | weak-focus | CRT | Blurry picture |
| 12 | multi-fault | PSU, CRT, RAM | "The whole thing's broken" |

Files: `tests/scenarios/*.json` + `tools/training/scenario_runner.py`.

---

### 7.4 — Scenario runner + browser UI wiring

**`tools/training/scenario_runner.py`**
Loads scenario JSON; posts each fault to the cabinet-bus API
(`/api/peripherals/{id}/fault` or `/api/mame/stuck_byte`); returns a
summary dict.

**Server endpoints (new):**
- `GET  /api/scenarios` — list all scenario metadata (id, title, difficulty)
- `POST /api/scenarios/{id}/apply` — apply all faults in the scenario
- `POST /api/scenarios/{id}/clear` — clear all faults in the scenario

**Browser UI additions (`ui/index.html` + `ui/app.js`):**
- Scenario dropdown + **Apply** / **Clear** buttons (top of page, always visible)
- Active-scenario banner showing title + affected subsystems
- Per-subsystem fault badges on the existing peripheral cards

---

### 7.5 — One-command launch (`tools/run-demo.sh`)

Update `tools/run-demo.sh` so a single command:
1. Starts the Flask cabinet-bus server in the background.
2. Launches MAME with Centipede + the `cabinet_bus` plugin +
   `cabinet_fault` BGFX chain.
3. Opens the browser at `http://localhost:5050`.

The script already exists; it needs the BGFX chain flag and a
browser-open call added.

---

### 7.6 — Unit tests

- `tools/training/test_scenario_runner.py` — load each scenario JSON,
  apply via mock cabinet-bus, verify API calls.
- Extend `tools/cabinet_bus/test_server.py` (or add) to cover
  `/api/scenarios/*` endpoints.

---

## Deliverables

| File | Status |
|------|--------|
| `vendor/mame/bgfx/chains/cabinet_fault.json` | NEW |
| `vendor/mame/bgfx/effects/cabinet_fault_crt.bgfx` | NEW |
| `vendor/mame/plugins/cabinet_bus/init.lua` | MODIFY (set_crt_fault cmd) |
| `tools/cabinet_bus/server.py` | MODIFY (scenarios + crt/apply) |
| `tools/training/scenario_runner.py` | NEW |
| `tools/training/test_scenario_runner.py` | NEW |
| `tests/scenarios/*.json` (12 scenarios) | NEW |
| `ui/index.html` + `ui/app.js` | MODIFY (scenario dropdown + banners) |
| `tools/run-demo.sh` | MODIFY (BGFX flag + browser open) |
| `wiki/Phases/Phase-7-*.md` | MODIFY (mark done) |

---

## What "Phase 7 done" means

- `tools/run-demo.sh` starts everything cleanly on a machine that has
  the MAME build and a Centipede ROM.
- Picking any of the 12 scenarios and clicking **Apply** causes an
  immediately visible change in the running MAME window and/or in-game
  behaviour within 1 second.
- Clicking **Clear** restores normal play without restarting MAME.
- All unit tests pass (`python -m pytest tools/ tests/`).

This is the prototype-quality milestone: compelling enough to show a
friend who has never heard of arcade fault simulation.

---

## What is deferred to Phase 8

- KiCad SVG schematic view (interactive PCB-level fault selection)
- PCB-photo view (clickable board photograph)
- Probe view (live waveform oscilloscope per net)
- Realism-weighted random scenario selection + scoring
- Hint/reveal system after timeout or surrender
- Full 20-30 scenario library

---

## Future work after Phase 8

- Tier 1 cabinets (Asteroids, Tempest, Battlezone, Missile Command,
  Black Widow). Each is months not years once Centipede is solid.
- Tier 4 (Area 51 / CoJag) as the marquee stretch goal.

---

## Navigation
← Previous: [Phase 6 — CRT + trackball + audio](Phase-6-CRT-Trackball-Audio.md) ·
Next: Phase 8 — Schematic/PCB/probe views + training scoring (planned)
