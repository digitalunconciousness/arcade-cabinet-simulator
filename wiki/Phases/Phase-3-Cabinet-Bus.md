# Phase 3 — Cabinet bus + minimal UI
**Status:** 🚧 not started
**Goal:** Stand up the cabinet bus described in
`arcade_cabinet_fault_simulator_plan.md` § "The cabinet bus", and put a
minimal UI on top so a user can pick a fault from the schematic-view UI
and have it actually flip a `FAULT_BUFFER.MODE` parameter inside a
running netlist. End-state: open the UI, click a pin on the sync
generator schematic, watch the simulated VSYNC waveform stop pulsing.
**Estimate:** 4–6 weekends per the project plan.
## What unblocks this phase
- Phase 1 (`FAULT_BUFFER`) is in MAME and verified.
- Phase 2 (sync generator + manifest) demonstrates that we can identify
  fault targets via `(refdes, pin) → fault_device_name` and modify them
  at netlist load time. Phase 3 makes that modification happen
  dynamically over a wire.
## Plan sketch
1. **Lua plugin** inside MAME that opens a TCP listener on a configurable
   port, accepts JSON messages over a length-prefixed framing, and
   exposes an API for:
   - `set_fault(fault_device, mode)` — flips `FB_*.MODE` at runtime.
     Implemented via the netlist runtime's parameter-set hooks.
   - `subscribe_net(name)` — streams logic-level changes back to the
     subscriber as `{t, name, value}` tuples.
   - `list_devices()` — returns the manifest content for the loaded netlist.
2. **Cabinet bus skeleton** — a Python or Node process that talks to the
   plugin and exposes a higher-level API to the UI. Same JSON schema as
   the plugin, plus session bookkeeping and (later) the peripheral
   models from Phase 4.
3. **Minimal UI** — a single web page rendered locally, served by the
   cabinet-bus process. SVG-based schematic of the Phase 2 sync gen
   (handwritten for now), each pin clickable, a panel for selecting a
   fault mode, and a live waveform display for one selected net.
4. **End-to-end demo** — run MAME loading the instrumented sync gen,
   click `V_LO.QC` in the UI, choose STUCK_LO, watch the VSYNC waveform
   freeze. Same scenario as the Phase 2 fault file but driven from the UI.
## Open questions
- Lua plugin lifecycle: do we run MAME standalone with `-plugin
  cabinet_bus`, or piggyback on the existing `console` plugin?
- JSON over TCP versus msgpack over TCP for the framing. JSON wins for
  debuggability; msgpack wins for waveform-stream throughput. Phase 3
  will likely start with JSON and revisit if a probe stream gets glitchy.
- UI stack: vanilla SVG + a tiny WebGL canvas for the waveform, or pull
  in a small framework like Svelte? For Phase 3 stay minimal.
## Deliverables to land in the same commit as the phase
- The Lua plugin source under `vendor/mame/plugins/cabinet_bus/` plus a
  patch file in `patches/`.
- The cabinet-bus process (Python or Node) under `tools/cabinet-bus/`.
- The minimal UI under `ui/`.
- A short demo recording or animated GIF of the rolling-picture fault
  triggered from the UI, attached to this wiki page.
- Updated `Phase-3-Cabinet-Bus.md`, `Home.md`, `Roadmap.md`.
- New ADRs as needed (likely one for the plugin protocol, one for the UI stack).
