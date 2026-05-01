# Arcade Cabinet Fault Simulator — wiki
Software simulator for a complete arcade cabinet (PCB + power supply +
monitor + trackball + coin mech + harness + lights + audio) that lets a
user inject realistic faults at any subsystem. Initial target is the Atari
Centipede.
The master plan is in [`arcade_cabinet_fault_simulator_plan.md`](../arcade_cabinet_fault_simulator_plan.md).
## Current status
**Phase 6 in progress — CRT/trackball/audio implementation started.**
Phase 6 now has working scaffolding in the codebase: new CRT/trackball/
audio peripheral models, CRT preview + trackball + audio controls in the
UI, initial shader set under `ui/shaders/`, and direct-push
`trackball_delta` plumbing through the cabinet-bus bridge.
Latest details: `Phases/Phase-6-CRT-Trackball-Audio.md`.

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
Current focus: **Phase 6** — CRT monitor + trackball + audio chain. The
largest single phase per the project plan: shader-level chassis fault
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
| 5 | [Address decoder + RAM](Phases/Phase-5-Address-Decoder-RAM.md) | ✅ complete |
| 5.5 | [RAM region (cell-level faults)](Phases/Phase-5.5-RAM-Region.md) | ✅ complete |
| 6 | [CRT + trackball + audio](Phases/Phase-6-CRT-Trackball-Audio.md) | 🚧 in progress |
| 7 | [Cabinet UI + training mode](Phases/Phase-7-Cabinet-UI-Training.md) | ⏳ planned |
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
