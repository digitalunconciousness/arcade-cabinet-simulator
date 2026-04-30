# Arcade Cabinet Fault Simulator — wiki
Software simulator for a complete arcade cabinet (PCB + power supply +
monitor + trackball + coin mech + harness + lights + audio) that lets a
user inject realistic faults at any subsystem. Initial target is the Atari
Centipede.
The master plan is in [`arcade_cabinet_fault_simulator_plan.md`](../arcade_cabinet_fault_simulator_plan.md).
## Current status
**Phase 3 complete (showable demo).** A browser GUI at
`http://127.0.0.1:5050` shows the sync generator schematic with eight
clickable fault-injection pins and live HSYNC/VSYNC waveforms. Click
`V_LO.QC`, pick STUCK_LO, and watch VSYNC freeze while HSYNC keeps
ticking — the rolling-picture fault, end-to-end.
Architecture: a small Flask cabinet-bus runs `nltool` per request
against a generated scenario file rather than embedding a long-running
Lua plugin inside MAME. That plugin work is deferred to a Phase 3.5
follow-up; the UI and protocol stay the same when we swap the backend.
Up next: Phase 4 — PSU model + simple peripherals (coin mech, buttons,
lighting, harness).
## Quick links
### Phases
- [Phase 0 — Bootstrap](Phases/Phase-0-Bootstrap.md) ✅
- [Phase 1 — Fault buffer](Phases/Phase-1-Fault-Buffer.md) ✅
- [Phase 2 — Sync generator](Phases/Phase-2-Sync-Generator.md) ✅
- [Phase 3 — Cabinet bus + UI](Phases/Phase-3-Cabinet-Bus.md) ✅
- [Phase 4 — PSU + peripherals](Phases/Phase-4-PSU-Peripherals.md) 🚧 planned
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
