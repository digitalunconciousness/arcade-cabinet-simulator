# Phase 5 — Address decoder + RAM region
**Status:** ✅ complete — Target B (address decoder) shipped here;
Target C (RAM region with bad-cell modeling) shipped in
[Phase 5.5](Phase-5.5-RAM-Region.md).
**Goal:** Two more PCB sub-circuits get netlist coverage:
- **Target B — Address decoder** (TM-182 sheet 2). The 74139/74138
  decoders that produce ROM, RAM, POKEY, EAROM, and video-RAM
  chip-selects. Faults make specific subsystems unreachable.
- **Target C — Working RAM region** (TM-182 sheet 3). The 2114 RAM
  chips, address mux, and data-bus buffers, with cell-level fault
  modeling. *Deferred to Phase 5.5; see "Out of scope" below.*
**Estimate:** 4–6 weekends. **Actual: 1 evening for Target B.**
## What landed
- `tests/netlist/centiped/address_decoder.cpp` — base netlist:
  74161 counter feeding a 74155A demux, producing four active-low
  chip-select lines `ROM_CSn`, `RAM_CSn`, `POKEY_CSn`, `EAROM_CSn`.
  Master clock 1 MHz (round-numbered stand-in for the real 1.512 MHz
  6502 bus rate).
- `build/instrumented/address_decoder.cpp` — preprocessor output with
  three `FAULT_BUFFER`s on the address-bus signals: `CLK.Q`,
  `ADDR_CTR.QA`, `ADDR_CTR.QB`.
- `build/instrumented/address_decoder.manifest.json` — three
  fault-eligible pins.
- `tests/netlist/centiped/scenarios/fault_addr_qb_stuck_lo.cpp` —
  fault scenario holding `FB_ADDR_CTR_QB` in STUCK_LO. ROM_CSn and
  RAM_CSn cycle at double rate; POKEY_CSn and EAROM_CSn never assert.
## Verification
| Run | ROM_CSn | RAM_CSn | POKEY_CSn | EAROM_CSn | Notes |
|---|---|---|---|---|---|
| Bare netlist (100 µs) | 52 | 54 | 54 | 53 | each line ~25 % active, exclusivity holds |
| Instrumented, NORMAL  | 52 | 54 | 54 | 53 | identical to bare |
| `FB_ADDR_CTR_QB` STUCK_LO | 102 | 103 | 4 | 4 | ROM/RAM 2×, POKEY/EAROM silent |
The exclusivity check (Python script verifying no two CS lines low
simultaneously) reports zero violations across 97 sampled time points
after settling.
## Architecture (representative)
```
1 MHz clock  ──► ADDR_CTR 74161 ──► QA ──► DEC.A
                                ──► QB ──► DEC.B
                  HI ──► DEC.C  (data tied high)
                  LO ──► DEC.G  (active-low enable)
                                  DEC 74155A
                                ──► Y0 → ROM_CSn
                                ──► Y1 → RAM_CSn
                                ──► Y2 → POKEY_CSn
                                ──► Y3 → EAROM_CSn
```
Real Centipede uses high-order address bits (A12..A15) and `/MEM_R`,
`/MEM_W` to gate the decoder. This rep uses 2 bits and a free-running
counter. Architectural shape (one decoder → mutually-exclusive
active-low CS lines) is faithful.
## Why a 74155A and not a 74139
The plan called for 74139 (the textbook arcade decoder). MAME 0.287's
`TTL_74139_GATE` truth table at `nlm_ttl74xx_lib.cpp:3312` has 4
outputs but only 1 timing value per `TT_LINE`, e.g.:
```
TT_LINE("0,0,0|0,1,1,1|14")
```
The truth-table parser (`nlid_truthtable.cpp:589`) requires
`times.size() == m_NO`, so loading the device fatals with "timing
count not matching". `TTL_74155A_GATE` has the same demux semantics
with a correctly-formed timing array (`|13,13,13,13`), so we use it.
A patch to fix 74139 upstream is a one-line-per-row sed (replicate
the timing value four times across `|14`, `|14,14,14,14`); we'll send
it to MAME if/when the address decoder grows beyond the rep stage.
## Gotchas
- `TTL_74155A_GATE` pin order: `B,A,G,C` for inputs (B is MSB, G is
  active-low enable, C is data). Output names are `Y0..Y3`. Easy to
  misread the data-sheet column order.
- `TTL_INPUT(LO, 0)` works as the always-low strobe but doesn't show
  up as an instrumentable pin in our manifest — the preprocessor only
  rewrites two-pin connections where both ends are pin refs (`X.Y`),
  not bare names.
- The preprocessor instrumented only the three actual signal lines
  (`CLK.Q`, `QA`, `QB`), not the static-config wiring. That's
  correct — we don't want fault buffers on power, enable, or
  data-tie-high pins.
## Target C → Phase 5.5
Target C (RAM region with bad-cell modeling) was split into a
dedicated [Phase 5.5](Phase-5.5-RAM-Region.md) sub-phase and is now
complete. The new `BAD_RAM_CELL` netlist device wraps an SRAM with
stuck-at fault injection at a configurable address, distinct from
`FAULT_BUFFER` (which only handles pin-level faults). See the
Phase 5.5 page for verification and architecture.
## Out of scope (still deferred)
- **PSU rail coupling.** The Phase 4 PSU model exposes a 5 V rail in
  Python state but doesn't yet feed into the netlist solver as
  `ANALOG_INPUT(VCC, ...)`. Brown-out faults from the PSU thus don't
  propagate to PCB symptoms. Hooking that up needs the cabinet bus to
  pass rail voltages into per-request `RunSpec`. Targeted for Phase 6
  alongside the CRT model (which also consumes rails).
- **UI multi-netlist support.** The browser GUI currently loads one
  manifest at boot (the sync generator). Adding a netlist-selector
  dropdown to the UI is a small follow-up; for now the address
  decoder is exercised via nltool directly.
## What unblocks Phase 6
- The address decoder lands as a second instrumented netlist alongside
  the sync generator, proving the pattern scales beyond one circuit.
- The fault scenario format (`build/instrumented/<x>.cpp` + appended
  `PARAM(FB_*.MODE, ...)` lines) handles arbitrary instrumented
  netlists with no preprocessor or cabinet-bus changes.
- Phase 6's CRT model can pull video timing (HSYNC/VSYNC from Phase 2)
  and chip-select pulses (POKEY_CSn from this phase) without further
  netlist work.
## Navigation
← Previous: [Phase 4 — PSU + peripherals](Phase-4-PSU-Peripherals.md) ·
Next: [Phase 5.5 — RAM region](Phase-5.5-RAM-Region.md) →
