# Phase 5 — Address decoder + RAM region
**Status:** 🚧 not started
**Goal:** Two more PCB sub-circuits get netlist coverage:
- **Target B — Address decoder** (TM-182 sheet 2). The 74139/74138
  decoders that produce ROM, RAM, POKEY, EAROM, and video-RAM
  chip-selects. Faults make specific subsystems unreachable —
  corrupting the playfield-RAM CS produces immediately recognizable
  graphics corruption.
- **Target C — Working RAM region** (TM-182 sheet 3). The 2114 RAM
  chips, address mux, and data-bus buffers. Bad-cell models inject
  faults at the storage-cell level, not just at the chip pins.
**Estimate:** 4–6 weekends per the project plan.
## Why these targets next
- They're the most common real-world fault categories on these boards.
  Address-decoder faults split out subsystems with high diagnostic
  value; bad RAM cells are the single most common cabinet failure.
- They build on Phase 2's pattern: 74xx-series TTL, schematic-faithful
  netlist, FAULT_BUFFER instrumentation through the existing
  preprocessor.
## Plan sketch
1. Transcribe sheet 2 of DP-182 into `tests/netlist/centiped/address_decoder.cpp`.
2. Transcribe sheet 3 of DP-182 into `tests/netlist/centiped/ram_region.cpp`.
3. Run the auto-instrumentation preprocessor; manifest grows.
4. Add a `BAD_RAM_CELL` netlist device (FAULT_BUFFER for storage
   cells; a data-bit address pair stuck-at).
5. Couple the PSU's 5 V rail (Phase 4) into the netlist as
   `ANALOG_INPUT(VCC, <psu_rail>)` so brown-out faults from the PSU
   propagate into PCB symptoms.
6. Demo: a bad RAM cell at one address producing visible graphics
   corruption.
## Deliverables to land in the same commit as the phase
- New netlist files for the address decoder and RAM region.
- New `BAD_RAM_CELL` device + patch.
- Updated manifest schema for storage-cell-level faults.
- UI extension: a memory-map view with clickable cell ranges.
- Updated wiki: this file's status, Home, Roadmap.
## Open questions
- Should `BAD_RAM_CELL` be its own device or a `FAULT_BUFFER` variant?
  The plan calls out cell-level faults as a separate primitive; likely
  a sibling device.
- How much of the 2114's behavior should be netlist vs functional?
  The 2114 is small enough (1024×4) to net-list completely if we want.
## Navigation
← Previous: [Phase 4 — PSU + peripherals](Phase-4-PSU-Peripherals.md) ·
Next: [Phase 6 — CRT + trackball + audio](Phase-6-CRT-Trackball-Audio.md) →
