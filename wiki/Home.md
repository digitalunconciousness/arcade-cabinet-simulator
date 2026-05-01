# Arcade Cabinet Fault Simulator — wiki
Software simulator for a complete arcade cabinet (PCB + power supply +
monitor + trackball + coin mech + harness + lights + audio) that lets a
user inject realistic faults at any subsystem. Initial target is the Atari
Centipede.
The master plan is in [`arcade_cabinet_fault_simulator_plan.md`](../arcade_cabinet_fault_simulator_plan.md).
## Current status
**Phase 7 complete — vertical-slice demo validated.**
Phase 6 is complete: CRT/trackball/audio peripheral models, Lua overlay
effects, WebAudio controls, and `trackball_delta` bridge plumbing all
landed. Phase 7 implements the full one-command demo loop:

- `tools/run-demo.sh` — launches MAME with the `cabinet_fault` BGFX chain
  and the cabinet-bus Flask server, then opens the browser automatically.
- 12 named fault scenarios (`tests/scenarios/*.json`) covering PSU sag,
  CRT faults, RAM glitches, address-decoder errors, and audio faults.
- UI scenario dropdown: pick a scenario, click **Apply**, fault takes
  effect in the running game within one second. Click **Clear** to reset.
- PSU watcher thread propagates voltage sag → CRT dim + stuck-byte
  transient automatically.
- 21-test suite in `tools/training/test_scenario_runner.py` (all pass).

Latest details: `Phases/Phase-7-Cabinet-UI-Training.md`.

Phase 5.5 (RAM region with cell-level fault modeling) remains complete:
A new `BAD_RAM_CELL` netlist device wraps a 16-cell SRAM with stuck-at
fault injection at a configurable address. The faulted cell refuses
writes and reads as 0/1/inverted while the other 15 cells behave
normally — the textbook "one bad RAM cell" symptom every arcade tech
recognizes. Detailed in `Phases/Phase-5.5-RAM-Region.md`.
Phase 5 itself (address decoder, Target B) shipped earlier this run; a
stuck-low fault on the QB address bit demonstrates the "sound and
high-score memory go dead, rest of the bus fine" symptom. See
`Phases/Phase-5-Address-Decoder-RAM.md`.
Current focus: **Phase 9** — desktop productization.
Phase 8 (schematic board packages + training surfaces) is complete:
the Centipede board package now contains real component/net data derived
from the instrumented MAME netlists, all 11 fault targets are mapped in
`fault_map.json`, the UI ships a full Board Inspector with component
browser, PCB-grid overview, and per-pin probe panel, and a coverage
validator checks scenario targets against board-package entries.

The next major program milestones are now explicit:
- Phase 9: downloadable desktop app for Linux/Windows/macOS instead of a manual server/browser workflow.
- Phase 10: full 3D cabinet digital twin with physically placed boards and service hotspots.
- Phase 11: diagnosis-and-repair training loop with virtual repairs and verification.
- Phase 12: physical parts/BOM/sourcing plan and simulator parity checks against a real cabinet.

## Phase index
| Phase | Title | Status |
|-------|-------|--------|
| 0 | [Bootstrap](Phases/Phase-0-Bootstrap.md) | ✅ complete |
| 1 | [Fault buffer](Phases/Phase-1-Fault-Buffer.md) | ✅ complete |
| 2 | [Sync generator](Phases/Phase-2-Sync-Generator.md) | ✅ complete |
| 3 | [Cabinet bus + UI](Phases/Phase-3-Cabinet-Bus.md) | ✅ complete |
| 3.5 | [MAME bridge](Phases/Phase-3.5-MAME-Bridge.md) | ✅ complete |
| 4 | [PSU + peripherals](Phases/Phase-4-PSU-Peripherals.md) | ✅ complete |
| 5 | [Address decoder + RAM](Phases/Phase-5-Address-Decoder-RAM.md) | ✅ complete |
| 5.5 | [RAM region (cell-level faults)](Phases/Phase-5.5-RAM-Region.md) | ✅ complete |
| 6 | [CRT + trackball + audio](Phases/Phase-6-CRT-Trackball-Audio.md) | ✅ complete |
| 7 | [Cabinet UI + training mode](Phases/Phase-7-Cabinet-UI-Training.md) | ✅ complete |
| 8 | [Schematic board packages + training surfaces](Phases/Phase-8-Schematic-Board-Package.md) | ✅ complete |
| 9 | [Desktop productization](Phases/Phase-9-Desktop-Productization.md) | ⏳ planned |
| 10 | [3D cabinet digital twin](Phases/Phase-10-3D-Cabinet-Digital-Twin.md) | ⏳ planned |
| 11 | [Interactive technician workflow](Phases/Phase-11-Interactive-Technician-Workflow.md) | ⏳ planned |
| 12 | [Physical prototype + parts plan](Phases/Phase-12-Physical-Prototype-Parts-Plan.md) | ⏳ planned |
Full schedule and tier-expansion plan: [Roadmap](Roadmap.md).
### Reference
- [Build notes](Build-Notes.md) — toolchain, build commands, audio config
- [Glossary](Glossary.md) — terminology cheat-sheet
- [References](References.md) — source materials (TM-182, DP-182, etc.)
- [Devices/FAULT_BUFFER](Devices/FAULT_BUFFER.md) — pin-level fault-injection buffer
- [Devices/BAD_RAM_CELL](Devices/BAD_RAM_CELL.md) — cell-level fault-injection SRAM
### Decisions
- [ADR-0001 — Wiki workflow](Decisions/ADR-0001-wiki-workflow.md)
## How to contribute to the wiki
Read [`README.md`](README.md). The TL;DR is: phase deliverables and wiki
updates land together in the same commit.
