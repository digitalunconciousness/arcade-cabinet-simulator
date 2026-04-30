# Arcade Cabinet Fault Simulator — wiki
Software simulator for a complete arcade cabinet (PCB + power supply +
monitor + trackball + coin mech + harness + lights + audio) that lets a
user inject realistic faults at any subsystem. Initial target is the Atari
Centipede.
The master plan is in [`arcade_cabinet_fault_simulator_plan.md`](../arcade_cabinet_fault_simulator_plan.md).
## Current status
**Phase 2 complete (representative pass).** The Centipede sync generator
is netlisted with chained 74161 counters and NAND-gate sync decode at the
real 12.096 MHz master clock. The auto-instrumentation preprocessor
generates an 8-entry manifest, a STUCK_LO fault on `FB_V_LO_QC` reproduces
the "no VSYNC / rolling picture" symptom, and HSYNC stays unaffected —
fault propagation is localized as designed. The netlist is
*representative*, not schematic-faithful; replace once TM-182 is on hand.
Up next: Phase 3 — cabinet bus + minimal UI. Lua TCP/JSON server inside
MAME, schematic-view UI with fault-inject controls, one waveform probe.
## Quick links
### Phases
- [Phase 0 — Bootstrap](Phases/Phase-0-Bootstrap.md) ✅
- [Phase 1 — Fault buffer](Phases/Phase-1-Fault-Buffer.md) ✅
- [Phase 2 — Sync generator](Phases/Phase-2-Sync-Generator.md) ✅
- [Phase 3 — Cabinet bus + UI](Phases/Phase-3-Cabinet-Bus.md) 🚧 planned
- [Roadmap](Roadmap.md)
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
