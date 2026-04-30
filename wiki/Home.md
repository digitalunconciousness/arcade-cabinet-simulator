# Arcade Cabinet Fault Simulator — wiki
Software simulator for a complete arcade cabinet (PCB + power supply +
monitor + trackball + coin mech + harness + lights + audio) that lets a
user inject realistic faults at any subsystem. Initial target is the Atari
Centipede.
The master plan is in [`arcade_cabinet_fault_simulator_plan.md`](../arcade_cabinet_fault_simulator_plan.md).
## Current status
**Phase 5 partial complete — Target B (address decoder) shipped; Target C
(RAM region with bad-cell modeling) split out to a Phase 5.5 follow-up.**
A representative Centipede address decoder netlist now produces four
active-low chip-select lines (ROM, RAM, POKEY, EAROM); a stuck-low fault
on the QB address bit demonstrates the textbook "sound and high-score
memory go dead, rest of the bus fine" symptom — ROM/RAM cycle at 2×,
POKEY/EAROM never assert. Detailed in `Phases/Phase-5-Address-Decoder-RAM.md`.
Up next: **Phase 6** — CRT monitor + trackball + audio chain. The
biggest single phase per the project plan: shader-level chassis fault
effects, trackball quadrature with fault categories, audio post-processing.
## Phase index
| Phase | Title | Status |
|-------|-------|--------|
| 0 | [Bootstrap](Phases/Phase-0-Bootstrap.md) | ✅ complete |
| 1 | [Fault buffer](Phases/Phase-1-Fault-Buffer.md) | ✅ complete |
| 2 | [Sync generator](Phases/Phase-2-Sync-Generator.md) | ✅ complete |
| 3 | [Cabinet bus + UI](Phases/Phase-3-Cabinet-Bus.md) | ✅ complete |
| 3.5 | [MAME bridge](Phases/Phase-3.5-MAME-Bridge.md) | ✅ complete |
| 4 | [PSU + peripherals](Phases/Phase-4-PSU-Peripherals.md) | ✅ complete |
| 5 | [Address decoder + RAM](Phases/Phase-5-Address-Decoder-RAM.md) | ✅ partial (5.5 deferred) |
| 6 | [CRT + trackball + audio](Phases/Phase-6-CRT-Trackball-Audio.md) | 🚧 next up |
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
