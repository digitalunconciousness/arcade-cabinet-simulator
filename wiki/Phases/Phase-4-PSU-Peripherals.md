# Phase 4 — PSU model + simple peripherals
**Status:** 🚧 not started
**Goal:** Add the first wave of cabinet-level peripheral models from
`arcade_cabinet_fault_simulator_plan.md`: power supply (real-ish
electrical model), coin mech, buttons, marquee/bezel lighting, and the
wiring harness that connects them. Each gets fault categories the user
can inject from the UI alongside the existing PCB-level faults.
**Estimate:** 6–8 weekends per the project plan.
## What unblocks this phase
- Phase 3 cabinet-bus protocol is in place: a JSON request can carry a
  fault dict and the UI renders the response. Extending that to
  `{peripherals: {...}}` is straightforward.
- The instrumentation manifest format already maps clickable UI regions
  to fault targets. We extend it with peripheral entries.
## Plan sketch
1. **PSU model** — Python module (no netlist solver involvement):
   - State: AC mains voltage, transformer turns, bridge state, filter-cap
     ESR, regulator state per rail.
   - Inputs: load current per rail (initially constant from a config; in
     a later phase the netlist's actual draw).
   - Outputs: rail voltage per rail.
   - Faults: bad bridge rectifier (half-wave), dried filter cap (high
     ripple), failed regulator, undervoltage from sagging mains, overload
     trip.
   - Couples back to the netlist by passing the +5 V rail value in as
     `ANALOG_INPUT(VCC, ...)` per scenario run. Cap-induced ripple becomes
     a small AC component on top.
2. **Coin mech** — pure state machine in Python: idle → coin-detected →
   validation → accept/reject. Faults: stuck switch (free credits), dirty
   contact (intermittent), jammed mech.
3. **Buttons** — trivial state with bounce. Faults: stuck closed, stuck
   open, intermittent, contact bounce.
4. **Marquee + bezel lighting** — fluorescent tube + ballast model.
   Faults: dead tube, bad ballast (slow start, flicker, hum), aging tube
   (dim, color shift).
5. **Wiring harness** — connects everything. Faults: open (broken wire),
   short (chafed), high resistance (corroded molex pin).
## UI extensions
- A second pane next to the schematic showing the cabinet (PSU, coin
  door, marquee, harness routing) with click-targets per peripheral.
- The existing fault-mode dropdown extends with peripheral-specific
  modes (the menu structure depends on the component).
- A new probe row for the PSU rail voltages.
## Deliverables to land in the same commit as the phase
- Python modules under `tools/peripherals/{psu,coin_mech,buttons,...}.py`.
- Schema extension to `manifest.json` for peripheral entries.
- UI updates (cabinet pane, peripheral fault dropdowns, rail probe).
- Updated wiki: this file's status, Home, Roadmap.
- ADRs as needed (e.g., how PSU rail voltage couples back to the netlist).
## Open questions
- Do we keep the PSU as a pure-Python model, or eventually netlist-ify
  the rectifier and regulator stages? The project plan defers this to v2.
- Should the harness be a single global object, or per-segment (PCB↔PSU,
  PSU↔monitor, etc.)? Per-segment is more realistic for fault categories
  but more UI surface. Probably per-segment.
