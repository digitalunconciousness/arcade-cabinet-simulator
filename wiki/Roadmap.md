# Roadmap
Phases are sized for evening/weekend pace with one developer plus
occasional EE consultation. Sourced from `arcade_cabinet_fault_simulator_plan.md`.
## Status legend
- ✅ complete
- 🚧 in progress
- ⏳ planned, not started
- 🧊 frozen / explicit non-goal for v1
## Phases
### ✅ Phase 0 — Bootstrap
2-3 weekends estimated. **Actual: 1 evening.**
Build MAME from source, run Centipede revision 3, get comfortable with
MAME's netlist runtime. See [Phase-0-Bootstrap](Phases/Phase-0-Bootstrap.md).
### ✅ Phase 1 — Fault buffer device + preprocessor scaffold
3-4 weekends estimated. **Actual: 1 evening.**
`FAULT_BUFFER` netlist device with NORMAL / STUCK_HI / STUCK_LO / OPEN
modes, registered into MAME and verified with nltool. Auto-instrumentation
preprocessor scaffold with CLI, manifest, unit tests. See
[Phase-1-Fault-Buffer](Phases/Phase-1-Fault-Buffer.md).
### ✅ Phase 2 — Sync generator netlist coverage
3-4 weekends estimated. **Actual: 1 evening (representative pass).**
Netlisted the Centipede sync generator (chained 74161s + NAND sync
decode), ran the auto-instrumentation preprocessor (8 fault-eligible
pins instrumented), and demonstrated a localized stuck-low fault on
`FB_V_LO_QC` that knocks out VSYNC while leaving HSYNC untouched. See
[Phase-2-Sync-Generator](Phases/Phase-2-Sync-Generator.md). Schematic-faithful pass
deferred until TM-182 is downloaded.
### ✅ Phase 3 — Cabinet bus + minimal UI
4-6 weekends estimated. **Actual: 1 evening.**
Flask cabinet-bus + vanilla-JS browser UI. Click a pin in the SVG
schematic, pick a fault mode, see the waveforms re-render. Demo recipe
in [Phase-3-Cabinet-Bus](Phases/Phase-3-Cabinet-Bus.md).
### ✅ Phase 3.5 — MAME bridge
**Actual: 1 evening.** A MAME Lua plugin
(`vendor/mame/plugins/cabinet_bus/`) accepts JSON-line commands over a
TCP socket; the Flask cabinet-bus exposes them as `/api/mame/*`
endpoints (`get_state`, `pause`, `resume`, `soft_reset`); the UI
shows a live emulator panel and switches state on demand. See
[Phase-3.5-MAME-Bridge](Phases/Phase-3.5-MAME-Bridge.md). WebSocket
streaming and netlist-into-centiped integration are still deferred to
later phases.
### ✅ Phase 4 — PSU model + simple peripherals
6-8 weekends estimated. **Actual: 1 evening.**
PSU with operator-adjustable 5 V trim pot + 5 fault modes, coin mech,
buttons, marquee, harness segments. Cabinet (peripherals) panel in the
UI with a trim slider, color-coded rail readouts, fault dropdowns.
See [Phase-4-PSU-Peripherals](Phases/Phase-4-PSU-Peripherals.md).
### ✅ Phase 5 — Address decoder (Target B)
4-6 weekends estimated. **Actual: 1 evening for the address decoder.**
Representative netlist with 74161 + 74155A producing four active-low
chip-selects (ROM/RAM/POKEY/EAROM); preprocessor instrumented; fault
scenario `fault_addr_qb_stuck_lo.cpp` reproduces a clean two-of-four
chip-select dropout. See
[Phase-5-Address-Decoder-RAM](Phases/Phase-5-Address-Decoder-RAM.md).
### ✅ Phase 5.5 — RAM region with cell-level fault modeling
**Actual: 1 evening.**
New `BAD_RAM_CELL` netlist device — 16-cell SRAM with `BAD_ADDR` +
`MODE` parameters that pin a single cell to stuck-at-0/1/inverted
state. Test netlist `tests/netlist/centiped/ram_region.cpp` walks
0..15 with write-then-read cycles; under STUCK_LO at BAD_ADDR=5 the DO
line dips LOW once per 16-address sweep while the other 15 cells read
back the written 1. See
[Phase-5.5-RAM-Region](Phases/Phase-5.5-RAM-Region.md).
### 🚧 Phase 6 — CRT monitor + trackball + audio chain
8-12 weekends. Largest single phase. Wells-Gardner 19K6100 chassis
model as shader effects, trackball quadrature with fault categories,
audio chain post-processing. See
[Phase-6-CRT-Trackball-Audio](Phases/Phase-6-CRT-Trackball-Audio.md).
### ⏳ Phase 7 — Cabinet UI + scenario library + training mode
8-12 weekends. v1 polish: cabinet-cutaway UI, KiCad SVG schematic,
PCB-photo view, probe view, training-mode runner with realism-weighted
scenarios. See
[Phase-7-Cabinet-UI-Training](Phases/Phase-7-Cabinet-UI-Training.md).
## Explicit non-goals (frozen for v1)
- 🧊 Generic any-board support beyond Centipede.
- 🧊 Full analog fault realism (resistive faults, thermal intermittents,
  capacitor degradation curves).
- 🧊 Gate-level netlist of 6502 or POKEY.
- 🧊 Reverse-engineering the Atari custom chips into TTL netlists.
## Future tier expansion
Tier 1 (1979-1983 Atari TTL — Asteroids, Tempest, Battlezone, Missile
Command, Black Widow): 2-4 months evening time per title once Centipede is
done. Tier 2 (Pac-Man, Galaga, Donkey Kong, Defender): 3-6 months. Tier 3
(JAMMA-era 80s/90s 2D): 4-8 months. Tier 4 (Area 51 / CoJag): 6-12 months,
mostly cabinet-level work plus lightgun-monitor coupling. Tier 5 (Naomi
and beyond): out of foreseeable scope.
