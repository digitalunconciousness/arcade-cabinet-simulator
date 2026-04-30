# Phase 5.5 — RAM region with cell-level fault modeling
**Status:** ✅ complete.
**Goal:** Pick up the deferred Target C from Phase 5 — model the working
RAM region with cell-level (single-address) fault injection that
`FAULT_BUFFER` can't express, because `FAULT_BUFFER` only operates on
pins, not on the storage element behind a pin.
**Estimate:** Bundled with Phase 5 (4–6 weekends original budget).
**Actual: 1 evening.**
## Why a new device
`FAULT_BUFFER` is the right primitive for "this pin can't move" — clock
lines, chip-selects, address bits, single data lines. It can't express
"this RAM cell at address 0x205 is stuck low while addresses 0x204 and
0x206 still work," which is the dominant arcade-board RAM symptom (a
single 2114 cell decays after decades of UV exposure / electromigration
and you see one column of stuck pixels in attract mode).
A pin-level fault on the RAM data output would manifest as "the entire
RAM is dead", which is the wrong failure mode and the wrong UI surface.
The new `BAD_RAM_CELL` device wraps a real SRAM with two extra
parameters: which address is faulty (`BAD_ADDR`) and which fault mode
applies there (`MODE`).
## What landed
- `vendor/mame/src/lib/netlist/devices/nld_bad_ram_cell.cpp` — 16 × 1
  SRAM with NORMAL / STUCK_HI / STUCK_LO / FLIP modes at a configurable
  `BAD_ADDR`. Uses the same `state_container<std::array<uint8_t, N>>`
  storage idiom as MAME's `RAM_2102A`. Pin map is RAM-flavored (CEQ
  active-low, RWQ low-for-write, A0..A3, DI, DO).
- Build registration in `scripts/src/netlist.lua`,
  `generated/lib_entries.hxx`, `generated/nld_devinc.h` (the same
  three-file pattern as Phase 1's FAULT_BUFFER).
- `tests/netlist/centiped/ram_region.cpp` — 16-cell test bench. A 74161
  address counter walks 0..15; a 7474 D-flop divides the master clock
  to alternate write / read; DI is tied high so every write stamps a 1
  into a fresh cell. After warm-up, every read returns the stored 1
  except at the faulted address.
- `patches/0003-Add-BAD_RAM_CELL-netlist-device-for-cell-level-RAM-f.patch`
  — exported MAME-tree commit so the device reapplies cleanly to a fresh
  MAME 0.287 clone.
- `docs/devices/bad_ram_cell.md` — device documentation.
## Verification
Run the test netlist for 100 µs, log `DO`, count edges:
```
build/instrumented/  $  nltool --cmd=run --time_to_run=0.0001 \
                            -l DO -l RWQ -l ADDR_QA -l ADDR_QB \
                            -l ADDR_QC -l ADDR_QD \
                            -D BAD_RAM_CELL_MODE=0 \
                            tests/netlist/centiped/ram_region.cpp
```
Results:
- **MODE=0 (NORMAL):** DO settles HIGH (~4 V) by t=1.3 µs and stays
  there for the rest of the 100 µs run. 6 transitions total — all
  during the first three address sweeps as cells warm up.
- **MODE=2 (STUCK_LO) at BAD_ADDR=5:** DO dips LOW for ~0.5 µs
  (one address cycle) every 8 µs (one full sweep through 16
  addresses at 2 MHz). 32 transitions total. Other 15 cells return
  the written 1 cleanly.
- **Period sanity check:** 2 MHz / 16 addresses = 125 kHz wrap, so
  one LOW dip every 8 µs. Observed dips at 10.77 µs, 18.77 µs,
  26.77 µs, 34.77 µs, … — exact 8 µs spacing modulo the per-cycle
  jitter from the BAD_RAM_CELL access delay (250 ns).
The device behaves as a real RAM with one defective storage cell would:
the bad cell refuses writes, every read returns the stuck value, all
other cells are unaffected.
## Architecture
```
   2 MHz CLK ─┬──► 74161 ADDR_CTR  ──► A0..A3 ──┐
              │                                 │
              └──► 7474 RWQ_FF (÷2) ──► RWQ ────┤
                                                │
                  HI ──► DI ─────────────────── │
                                                ▼
                                            BAD_RAM_CELL
                                            ┌─ BAD_ADDR=5
                                            └─ MODE=0/1/2/3
                                                │
                                                ▼ DO
```
The 7474 self-loop (`QQ → D`) is a textbook divide-by-2: each clock
edge toggles Q, so RWQ alternates write / read on every address. The
74161 advances on every clock, so each address gets one write cycle
followed by one read cycle on every other sweep. After the first
~few sweeps every cell has been written at least once and DO behavior
is purely a function of the bad-cell mode.
This v1 model is a single-bit, 16-cell chip. The full Centipede
working RAM region (1024 × 4) chains four BAD_RAM_CELL instances on a
shared address bus, one per data bit. A future revision either widens
`NUM_CELLS` and `m_A` to 1024 cells × 4 bits, or instantiates four
copies in a Centipede-specific composite netlist.
## Why not extend FAULT_BUFFER?
Considered briefly. A FAULT_BUFFER on the RAM's data line is gated by
that line's value at the moment the fault asserts — it can't introspect
the address bus to decide whether *this* read should be faulted. We'd
need a netlist primitive that knows about the address, which is
basically what BAD_RAM_CELL is. Cleaner to make it a first-class device
than to cobble together address-decoded gating around FAULT_BUFFER.
## Gotchas
- **VCC/GND auto-connect.** Like FAULT_BUFFER, BAD_RAM_CELL declares
  `@VCC,@GND` in its `NETLIB_DEVICE_IMPL`. Do **not** add explicit
  `NET_C(VCC, U_RAM.VCC)` lines or you get
  `FATAL: Input U_RAM.VCC already connected` at parse time.
- **Stuck-cell writes are dropped.** A real bad cell in physical SRAM
  retains whatever its silicon has decayed to; you can't reprogram it.
  The model matches: writes to a faulted address are silently
  discarded. If the cell is later "healed" (MODE flipped back to
  NORMAL at runtime), it returns whatever was last successfully
  written *before* the fault, which is 0 if no successful write ever
  landed at that address.
- **Address-counter glitch on the first write.** Because both the
  address counter and the RWQ flop clock from the same master CLK
  edge, the address has a 25 ns transition window during which RWQ is
  also transitioning. The BAD_RAM_CELL handler triggers on any input
  change and resolves to the steady-state values within 250 ns
  (`ACCESS_DELAY`), so this is not visible in the output trace, but
  it does mean the device's internal state may briefly see a
  half-toggled address before settling. Fine for a behavioral
  fault-injection device; would be a problem for a SPICE-level
  timing model.
## What unblocks downstream phases
- The instrumented `address_decoder.cpp` from Phase 5 already wires
  `RAM_CSn`. A future scenario can drive a real BAD_RAM_CELL off
  `RAM_CSn` and the existing 6502 bus mock to demonstrate "RAM
  decay" symptoms in the cabinet UI.
- Phase 6's CRT model can pull video-RAM cell-level faults using the
  same device wired into the video address bus. Bad video-RAM cells
  produce the canonical column-of-glitches symptom the project plan
  calls out as a v1 demo.
- Phase 7's training-mode scenario library needs cell-level RAM faults
  for at least three of the listed Centipede service-call symptoms
  (attract-mode glitches, frozen high-score, single-pixel column).
  Now achievable.
## Navigation
← Previous: [Phase 5 — Address decoder + RAM](Phase-5-Address-Decoder-RAM.md) ·
Next: [Phase 6 — CRT + trackball + audio](Phase-6-CRT-Trackball-Audio.md) →
