# Arcade Cabinet Fault Simulator — wiki

Software simulator for a complete arcade cabinet (PCB + power supply +
monitor + trackball + coin mech + harness + lights + audio) that lets a
user inject realistic faults at any subsystem. Initial target is the Atari
Centipede.
The earlier plan (v0.2) is [`arcade_cabinet_fault_simulator_plan.md`](../arcade_cabinet_fault_simulator_plan.md).

> **Superseded by PLAN v0.3 (2026-11-09).** The plan of record is [`docs/PLAN_v3.md`](../docs/PLAN_v3.md).
> The Stage 0 truth audit ran every fault below against the live game, headless, in a build made from this repo.
> Most of them don't change the running game, so the phase statuses in the table were corrected to what the evidence
> shows. What is real, mocked and unproven: [`docs/STATUS.md`](../docs/STATUS.md). Per fault:
> [`docs/FAULT_AUDIT.md`](../docs/FAULT_AUDIT.md).

## Status before PLAN v0.3 (as written at the time)

**Phase 9 complete — Linux desktop shell shipped; live fault diagnostics added.**
The simulator now runs as a Tauri desktop app that orchestrates the full
local runtime instead of relying on a manually-started browser session.

- `src-tauri/src/lib.rs` boots `Xvfb :99`, launches MAME with the
  `cabinet_bus` plugin, starts the `arcade-sim-server` sidecar, waits for
  `/api/health`, then navigates the WebView to the live UI.
- `ui/splash.html` shows boot-stage progress and boot errors while the
  desktop app starts.
- `build-release.sh` is the canonical command to rebuild the full AppImage and
  deploy it to `~/Applications/`. The top-level `make` target is wired to the
  same rebuild-and-deploy flow. Both wrap `cargo tauri build` with the
  required `NO_STRIP=1` and `APPIMAGE_EXTRACT_AND_RUN=1` flags and run the
  PyInstaller sidecar build automatically via the `beforeBuildCommand` hook.
- Real-time MAME controls are desktop-first: `ui/app.js` sends input
  through `window.__TAURI__.core.invoke(...)`, and Rust forwards commands
  directly to the MAME plugin socket on `127.0.0.1:5051`.
- Boot diagnostics are written to `/tmp/arcade-sim-boot.log`, which makes
  App Center launch failures debuggable without a terminal.
- **Live fault diagnostics:** The MAME stats panel now shows a real-time
  *Stuck bytes* counter (increments as RAM fault bytes accumulate) and a
  *CRT overlay* indicator that reflects the active shader effect name and
  brightness. Both turn amber when a fault is active.
- **DIP Switches:** A *DIP Switches…* button in the MAME controls panel opens
  a modal with the full Centipede DIP switch list. Each switch renders as a
  labelled dropdown wired to `GET /api/mame/dip_switches` and
  `POST /api/mame/dip_switch`, backed by the Lua plugin's `ioport` enumeration.

Latest details: `Phases/Phase-9-Desktop-Productization.md`.

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
Current focus: **Phase 10** — 3D cabinet digital twin.
Phase 8 (schematic board packages + training surfaces) is complete:
the Centipede board package now contains real component/net data derived
from the instrumented MAME netlists, all 11 fault targets are mapped in
`fault_map.json`, the UI ships a full Board Inspector with component
browser, PCB-grid overview, and per-pin probe panel, and a coverage
validator checks scenario targets against board-package entries.

The next major program milestones are now explicit:

- Phase 10: full 3D cabinet digital twin with physically placed boards and service hotspots.
- Phase 11: diagnosis-and-repair training loop with virtual repairs and verification.
- Phase 12: physical parts/BOM/sourcing plan and simulator parity checks against a real cabinet.

## Phase index

| Phase | Title | Status after the Stage 0 audit |
| ----- | ----- | ------ |
| 0 | [Bootstrap](Phases/Phase-0-Bootstrap.md) | built; the patch series only applied to the pinned tag after a Stage 0 fix (ADR-0010) |
| 1 | [Fault buffer](Phases/Phase-1-Fault-Buffer.md) | works in standalone nltool only |
| 2 | [Sync generator](Phases/Phase-2-Sync-Generator.md) | representative netlist, standalone nltool only; never in the game |
| 3 | [Cabinet bus + UI](Phases/Phase-3-Cabinet-Bus.md) | legacy Flask UI; retired by PLAN v0.3 |
| 3.5 | [MAME bridge](Phases/Phase-3.5-MAME-Bridge.md) | partly: 8 plugin commands are committed; input, CRT and DIP commands are in no commit |
| 4 | [PSU + peripherals](Phases/Phase-4-PSU-Peripherals.md) | Python state models (mocked); only a rail below 4.7 V reaches the game, as one stuck tile |
| 5 | [Address decoder + RAM](Phases/Phase-5-Address-Decoder-RAM.md) | representative netlist, standalone nltool only |
| 5.5 | [RAM region (cell-level faults)](Phases/Phase-5.5-RAM-Region.md) | `BAD_RAM_CELL` works in standalone nltool only |
| 6 | [CRT + trackball + audio](Phases/Phase-6-CRT-Trackball-Audio.md) | doesn't reach the game: CRT and trackball commands are rejected; audio is a browser test tone |
| 7 | [Cabinet UI + training mode](Phases/Phase-7-Cabinet-UI-Training.md) | scenarios run; 3 of 12 change the game and none shows its described symptom (see FAULT_AUDIT) |
| 8 | [Schematic board packages + training surfaces](Phases/Phase-8-Schematic-Board-Package.md) | the board package fails to load (`fault_map.json` has a key the loader rejects), and no launcher points at it |
| 9 | [Desktop productization](Phases/Phase-9-Desktop-Productization.md) | Linux-only Tauri app; superseded by ADR-0011 |
| 10 | [3D cabinet digital twin](Phases/Phase-10-3D-Cabinet-Digital-Twin.md) | replaced by PLAN v0.3 Stage 4 |
| 11 | [Interactive technician workflow](Phases/Phase-11-Interactive-Technician-Workflow.md) | replaced by PLAN v0.3 Stage 5 |
| 12 | [Physical prototype + parts plan](Phases/Phase-12-Physical-Prototype-Parts-Plan.md) | not scheduled in PLAN v0.3 |

Full schedule and tier-expansion plan: [Roadmap](Roadmap.md).

### Reference

- [Build notes](Build-Notes.md) — toolchain, build commands, audio config
- [Glossary](Glossary.md) — terminology cheat-sheet
- [References](References.md) — source materials (TM-182, DP-182, etc.)
- [Devices/FAULT_BUFFER](Devices/FAULT_BUFFER.md) — pin-level fault-injection buffer
- [Devices/BAD_RAM_CELL](Devices/BAD_RAM_CELL.md) — cell-level fault-injection SRAM

### Decisions

- [ADR-0001 — Wiki workflow](Decisions/ADR-0001-wiki-workflow.md)
- [ADR-0009 — Desktop shell: Tauri](Decisions/ADR-0009-Desktop-Shell-Tauri.md) (superseded by ADR-0011)
- [ADR-0010 — Pin MAME and keep the patch series applying to it](Decisions/ADR-0010-Pin-MAME.md)
- [ADR-0011 — Native shell direction](Decisions/ADR-0011-Native-Shell-Direction.md)
- [ADR-0012 — ROMs, romset and what CI runs against](Decisions/ADR-0012-ROM-Policy.md)

## How to contribute to the wiki

Read [`README.md`](README.md). The TL;DR is: phase deliverables and wiki
updates land together in the same commit.
