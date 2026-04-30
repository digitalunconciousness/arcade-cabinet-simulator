# Arcade Cabinet Fault Simulator — wiki
Software simulator for a complete arcade cabinet (PCB + power supply +
monitor + trackball + coin mech + harness + lights + audio) that lets a
user inject realistic faults at any subsystem. Initial target is the Atari
Centipede.
The master plan is in [`arcade_cabinet_fault_simulator_plan.md`](../arcade_cabinet_fault_simulator_plan.md).
## Current status
**Phase 3.5 complete.** A MAME Lua plugin (`vendor/mame/plugins/cabinet_bus/`)
opens a TCP listener; the Flask cabinet-bus proxies
`get_state / pause / resume / soft_reset` to it; the browser UI
shows a live "Centipede emulator (MAME)" panel with ROM name, frame
counter, and pause/resume/reset buttons that drive a running
emulator next to the existing sync-generator fault demo.
Up until Phase 3.5, the demo was: click a pin in the schematic, see
VSYNC freeze. Now: that demo PLUS a real Centipede running in MAME
in a separate window, controllable from the same browser tab.
Up next: Phase 4 — PSU model + simple peripherals (coin mech, buttons,
lighting, harness).
## Quick links
### Phases
- [Phase 0 — Bootstrap](Phases/Phase-0-Bootstrap.md) ✅
- [Phase 1 — Fault buffer](Phases/Phase-1-Fault-Buffer.md) ✅
- [Phase 2 — Sync generator](Phases/Phase-2-Sync-Generator.md) ✅
- [Phase 3 — Cabinet bus + UI](Phases/Phase-3-Cabinet-Bus.md) ✅
- [Phase 3.5 — MAME bridge](Phases/Phase-3.5-MAME-Bridge.md) ✅
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
