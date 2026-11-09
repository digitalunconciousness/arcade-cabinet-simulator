# ADR-0013: The fault engine is a Lua plugin in this repo, spoken to over SCP v1

**Status:** accepted
**Date:** 2026-11-09
**Deciders:** project owner (PLAN v0.3, Stage 1)

## Context

The legacy `cabinet_bus` plugin lived only as `patches/0002`. The working copy on the maintainer's machine drifted from
it, so the commands the app relied on were in no commit (Stage 0 audit). Its one live fault, `stuck_byte`, rewrote a
cell after each frame and lost to the game's own writes.

## Decision

- The fault engine is the `cabsim` plugin in `plugin/cabsim/`, loaded with
  `-pluginspath "<mame>/plugins;<repo>/plugin" -plugin cabsim`. Editing it needs no patch and no rebuild. C++ goes into
  `patches/` only where Lua can't reach (ADR-0014).
- Faults are primitives applied at the emulated interfaces the game's code uses: memory read/write taps, ROM regions,
  CPU input lines, device clocks, input ports. They are game-agnostic; every parameter is an explicit tag, range,
  region or port. Active faults are re-applied after a power cycle.
- Faults that MAME's functional emulation can't reach at the hardware level are applied to the frame the plugin
  exports (`sync_timing`) and labelled Tier B.
- The app and the plugin talk over **Sim Control Protocol v1** (`docs/protocol/scp-v1.md`): newline-delimited JSON over
  a local TCP port given in `CABSIM_PORT`. Effect tests use the plugin's timeline mode (`CABSIM_SCRIPT`) instead, which
  is frame-exact and needs no socket.
- `cabinet_bus` stays in `patches/0002` for the legacy Tauri app until it leaves `main` (ADR-0011).

## Consequences

- A fault exists only if a primitive and an effect test exist for it (PLAN v0.3, principle 1).
- Measured cost (`evidence/stage1/benchmark.json`): taps on the hottest RAM cost about a quarter of the speed and
  still run ~18x real time on a 2.1 GHz Xeon vCPU. The Stage 2 spike re-measures on a Windows laptop.
- SCP v1 serves one client per MAME session in Stage 1. Reconnects and frame streaming are Stage 2 work.
