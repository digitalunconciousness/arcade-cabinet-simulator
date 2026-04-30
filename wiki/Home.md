# Arcade Cabinet Fault Simulator — wiki
Software simulator for a complete arcade cabinet (PCB + power supply +
monitor + trackball + coin mech + harness + lights + audio) that lets a
user inject realistic faults at any subsystem. Initial target is the Atari
Centipede.
The master plan is in [`arcade_cabinet_fault_simulator_plan.md`](../arcade_cabinet_fault_simulator_plan.md).
## Current status
**Phase 4 complete.** The browser GUI now has a Cabinet (peripherals)
panel with cards for the PSU, coin mech, marquee, buttons, and harness
segments. The PSU card exposes the operator-adjustable 5 V trim pot as
a live slider, alongside fault dropdowns for each peripheral. Trim
over-adjustment color-warns the rail readout; some faults
(`failed_regulator`, `overload_trip`) override the trim entirely — just
like the real hardware.
Up next: **Phase 5** — address decoder + RAM region netlist coverage.
See `Phases/Phase-5-Address-Decoder-RAM.md` for the goal and plan.
## Phase index
| Phase | Title | Status |
|-------|-------|--------|
| 0 | [Bootstrap](Phases/Phase-0-Bootstrap.md) | ✅ complete |
| 1 | [Fault buffer](Phases/Phase-1-Fault-Buffer.md) | ✅ complete |
| 2 | [Sync generator](Phases/Phase-2-Sync-Generator.md) | ✅ complete |
| 3 | [Cabinet bus + UI](Phases/Phase-3-Cabinet-Bus.md) | ✅ complete |
| 3.5 | [MAME bridge](Phases/Phase-3.5-MAME-Bridge.md) | ✅ complete |
| 4 | [PSU + peripherals](Phases/Phase-4-PSU-Peripherals.md) | ✅ complete |
| 5 | [Address decoder + RAM](Phases/Phase-5-Address-Decoder-RAM.md) | 🚧 next up |
| 6 | [CRT + trackball + audio](Phases/Phase-6-CRT-Trackball-Audio.md) | ⏳ planned |
| 7 | [Cabinet UI + training mode](Phases/Phase-7-Cabinet-UI-Training.md) | ⏳ planned |
Full schedule and tier-expansion plan: [Roadmap](Roadmap.md).
### Reference
- [Build notes](Build-Notes.md) — toolchain, build commands, audio config
- [Glossary](Glossary.md) — terminology cheat-sheet
- [References](References.md) — source materials (TM-182, DP-182, etc.)
- [Devices/FAULT_BUFFER](Devices/FAULT_BUFFER.md) — fault-injection buffer
### Decisions
- [ADR-0001 — Wiki workflow](Decisions/ADR-0001-wiki-workflow.md)
## How to contribute to the wiki
Read [`README.md`](README.md). The TL;DR is: phase deliverables and wiki
updates land together in the same commit.
