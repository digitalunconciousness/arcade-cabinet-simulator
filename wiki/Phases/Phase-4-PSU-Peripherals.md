# Phase 4 — PSU model + simple peripherals
**Status:** ✅ complete
**Goal:** First wave of cabinet-level peripheral models — power supply
(with the operator-adjustable 5 V trim pot the real boards ship with),
coin mech, panel buttons, marquee tube, and wiring harness segments.
Each gets fault categories the user can inject from the UI alongside
the existing PCB-level faults.
**Estimate:** 6–8 weekends. **Actual: 1 evening.**
## What landed
- `tools/peripherals/models.py` — five behavioral classes plus a
  `PeripheralRegistry` that owns the cabinet inventory:
  - **PowerSupply** — adjustable 5 V trim pot (default 5.05 V, range
    4.5–5.5 V) plus five fault modes: `bad_rectifier` (rail droops
    ~30 % with massive ripple), `dried_filter_cap` (high ripple),
    `failed_regulator` (pass element shorted, rail floats up to ~7.8 V
    and the trim pot stops mattering), `sagging_mains` (all rails
    proportionally low), `overload_trip` (rails collapse to 0 V).
  - **CoinMech** — idle/accept/reject state machine, faults:
    `stuck_switch` (free credits stream), `dirty_contact`,
    `jammed_mech`, `miscalibrated`.
  - **Button** — per-input fault model: `stuck_closed`, `stuck_open`,
    `intermittent`, `bouncy`, `slow_release`. Three buttons in the
    default registry: BTN_START1, BTN_START2, BTN_FIRE.
  - **Marquee** — fluorescent ballast model with `dead_tube`,
    `ballast_slow_start`, `ballast_flicker`, `ballast_hum`, and
    `aging_tube`.
  - **HarnessSegment** — wiring between two endpoints. Faults:
    `open`, `short_to_gnd`, `short_to_5v`, `high_resistance`,
    `chafed`. Default registry has four segments
    (PSU↔PCB, PSU↔Monitor, PSU↔Marquee, PCB↔Panel).
- `tools/peripherals/test_models.py` — 19 unit tests covering trim-pot
  range checks, the trim/fault interaction, every fault state
  transition, and the registry routing logic.
- `tools/cabinet_bus/server.py` — five new endpoints under
  `/api/peripherals/*` for state, fault, adjust, reset, coin.
- `ui/index.html` + `ui/style.css` + `ui/app.js` — new
  "Cabinet (peripherals)" panel above the schematic, with cards per
  peripheral. PSU card has rail readouts (color-coded ±5 %/±10 %),
  ripple value, and a 5 V trim slider.
## The trim-pot story
Real arcade PSUs let the operator nudge the +5 V rail with a small
pot (typically 4.5–5.5 V). Sweet spot is ~5.05 V at the PCB. Operators
crank it up to mask voltage drop from harness corrosion or a sagging
PSU; works short-term but stresses TTL chips when the underlying fault
is later fixed.
The simulator captures this interaction:
- The trim pot is a first-class adjustable parameter, not a fault.
- `sagging_mains` and `bad_rectifier` scale the trimmed value.
- `failed_regulator` overrides the trim entirely — the pass element is
  shorted, so the pot's no longer in the control loop.
- `overload_trip` collapses every rail to 0 V regardless.
- The UI rail readouts color-warn outside ±5 % of nominal and
  color-bad outside ±10 %, so over-trimming to mask one fault is
  visually obvious.
## Demo recipe
```bash
cd /home/jackie/arcade-sim
./tools/cabinet_bus/start.sh
# Open http://127.0.0.1:5050 in a browser.
```
Try:
1. Slide the **5 V trim pot** to 5.30 V — rail turns yellow.
2. Push it to 5.50 V — red.
3. Drop trim back to 5.05 V, apply `failed_regulator` — rail jumps to
   7.80 V regardless of trim. The "pass element shorted" failure mode.
4. Reset, apply `bad_rectifier` — rail droops to 3.5 V and ripple
   jumps to 1800 mV pp.
5. Marquee → `dead_tube`. Visible state goes to "off".
6. Coin mech → `stuck_switch`. Credits start streaming.
7. Hit **Reset all peripherals**.
## Smoke-test verification
```bash
curl -s http://127.0.0.1:5050/api/peripherals/state \
  | python -c "import sys,json; d=json.load(sys.stdin); print(len(d['peripherals']),'peripherals')"
# 10 peripherals
curl -s -X POST http://127.0.0.1:5050/api/peripherals/adjust \
  -H 'Content-Type: application/json' \
  -d '{"id":"PSU1","param":"trim_5v","value":5.30}' \
  | python -c "import sys,json;d=json.load(sys.stdin); print('5V rail:', d['rails']['5V'])"
# 5V rail: 5.3
curl -s -X POST http://127.0.0.1:5050/api/peripherals/fault \
  -H 'Content-Type: application/json' \
  -d '{"id":"PSU1","fault":"failed_regulator"}' \
  | python -c "import sys,json;d=json.load(sys.stdin); print('5V rail:', d['rails']['5V'])"
# 5V rail: 7.8  ← trim overridden
```
## Gotchas
- The peripheral models are pure Python state; they don't yet feed
  back into the netlist solver. A bad PSU rail won't (yet) cause the
  sync generator's HSYNC/VSYNC waveforms to misbehave. Coupling the
  PSU's 5 V output to `ANALOG_INPUT(VCC, ...)` is Phase 5/6 work.
- The UI polls `/api/peripherals/state` every 2 seconds — that's what
  makes `stuck_switch` look like it's streaming credits.
- `failed_regulator` ignores the trim pot because the pot is a
  feedback divider, useless when the pass element it feeds is shorted.
## Out of scope (deferred)
- Coupling PSU rail voltage back into the netlist solver — Phase 5/6.
- Real-time button press synthesis (currently buttons only carry fault
  state).
- Per-segment harness coupling: a harness `open` between PSU and
  Monitor should make the monitor go dark — Phase 6.
## What unblocks Phase 5
- The `/api/peripherals/*` protocol is established and exercised by a
  real UI. Phase 5's address-decoder/RAM faults will surface through
  the existing `/api/run` since they're netlist-side; the cabinet bus
  already knows how to render their results.
## Navigation
← Previous: [Phase 3.5 — MAME bridge](Phase-3.5-MAME-Bridge.md) ·
Next: [Phase 5 — Address decoder + RAM](Phase-5-Address-Decoder-RAM.md) →
