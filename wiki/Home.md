# Arcade Cabinet Fault Simulator — wiki
Software simulator for a complete arcade cabinet (PCB + power supply +
monitor + trackball + coin mech + harness + lights + audio) that lets a
user inject realistic faults at any subsystem. Initial target is the Atari
Centipede.
The master plan is in [`arcade_cabinet_fault_simulator_plan.md`](../arcade_cabinet_fault_simulator_plan.md).
## Current status
**Phase 1 complete.** `FAULT_BUFFER` netlist device is implemented,
verified, documented, and shipped as a portable patch series on top of
upstream MAME. The auto-instrumentation preprocessor scaffold is in place.
Up next: Phase 2 — netlist coverage of the Centipede sync generator (the
TTL counter chain on schematic sheets 4–5 that produces HSYNC, VSYNC, and
timing signals).
## Quick links
### Phases
- [Phase 0 — Bootstrap](Phases/Phase-0-Bootstrap.md) ✅
- [Phase 1 — Fault buffer](Phases/Phase-1-Fault-Buffer.md) ✅
- [Phase 2 — Sync generator](Phases/Phase-2-Sync-Generator.md) 🚧 planned
- [Roadmap](Roadmap.md)
### Reference
- [Build notes](Build-Notes.md) — toolchain, build commands, audio config
- [Glossary](Glossary.md) — terminology cheat-sheet
- [Devices/FAULT_BUFFER](Devices/FAULT_BUFFER.md) — fault-injection buffer
### Decisions
- [ADR-0001 — Wiki workflow](Decisions/ADR-0001-wiki-workflow.md)
## How to contribute to the wiki
Read [`README.md`](README.md). The TL;DR is: phase deliverables and wiki
updates land together in the same commit.
