# BAD_RAM_CELL
Cell-level fault-injection SRAM for the MAME netlist solver.
Source: `vendor/mame/src/lib/netlist/devices/nld_bad_ram_cell.cpp`
Build registration: `vendor/mame/scripts/src/netlist.lua`,
`vendor/mame/src/lib/netlist/generated/lib_entries.hxx`,
`vendor/mame/src/lib/netlist/generated/nld_devinc.h`
## Purpose
A small (16 × 1) static RAM with first-class support for a stuck-at
fault that affects exactly one configurable address. All other cells
behave like a normal SRAM. The fault-injection surface is two runtime
parameters, `BAD_ADDR` and `MODE`, mirroring the
`FAULT_BUFFER` MODE convention.
This device exists because pin-level faults (the FAULT_BUFFER primitive)
can't express the dominant RAM-decay symptom: one storage cell is
defective, the rest of the chip is fine. A FAULT_BUFFER on the RAM data
line would force *every* read to return the stuck value, which is the
wrong failure mode for the cabinet-fault UI.
## Modes
| MODE | Name      | Behavior at BAD_ADDR                                      |
|------|-----------|-----------------------------------------------------------|
| 0    | NORMAL    | All cells behave like normal SRAM. No fault active.       |
| 1    | STUCK_HI  | Reads at BAD_ADDR return 1; writes at BAD_ADDR are dropped. |
| 2    | STUCK_LO  | Reads at BAD_ADDR return 0; writes at BAD_ADDR are dropped. |
| 3    | FLIP      | Reads at BAD_ADDR return the stored bit XORed with 1; writes are dropped. |
Cells outside `BAD_ADDR` are always read/write-correct regardless of MODE.
Any value outside 0–3 is treated as NORMAL.
## Pin map
- `A0..A3` — 4 address inputs (16 addressable cells).
- `CEQ`    — chip enable, **active low**. While CEQ is high the
  device is unselected; DO holds its previous value.
- `RWQ`    — read/write, **low = write**, high = read. Same convention as
  RAM_2102A.
- `DI`     — data input (1 bit, sampled on writes).
- `DO`     — data output (1 bit, drives the destination net with a
  250 ns access delay approximating a 2114).
- `VCC`    — power, **auto-connected** (`@VCC` in the device declaration).
- `GND`    — ground, **auto-connected** (`@GND` in the device declaration).
Because power is auto-connected, **do not** add `U_RAM.VCC` or `U_RAM.GND`
to your own `NET_C(...)` lines. Doing so triggers a fatal
`Input U_RAM.VCC already connected` at netlist load time.
## Parameters
- `BAD_ADDR` (`param_int_t`, default `0`) — the cell address (0..15) whose
  storage is faulty. Outside that address all cells behave normally.
- `MODE` (`param_int_t`, default `0`) — the runtime fault mode (table above).
## Storage
The 16 cells are persisted in a `state_container<std::array<uint8_t, 16>>`,
the same pattern MAME's existing `RAM_2102A` (`nld_2102a.cpp`) uses, so
the device participates in netlist save/load like any other RAM. Reset
zeroes all cells.
## Usage in a netlist
```cpp
#include "netlist/devices/net_lib.h"

NETLIST_START(main)
{
    SOLVER(Solver, 48000)
    ANALOG_INPUT(VCC, 5.0)

    TTL_INPUT(HI, 1)
    TTL_INPUT(LO, 0)
    NET_C(VCC, HI.VCC, LO.VCC)
    NET_C(GND, HI.GND, LO.GND)

    MAINCLOCK(CLK, 2000000)
    TTL_74161(ADDR_CTR)        // walks 0..15 on the bus
    NET_C(CLK.Q, ADDR_CTR.CLK)
    // ... wire ADDR_CTR ENP/ENT/CLRQ/LOADQ/A..D high/low ...

    BAD_RAM_CELL(U_RAM,
                 LO,                    // CEQ — always selected
                 ADDR_CTR.QA,           // A0
                 ADDR_CTR.QB,           // A1
                 ADDR_CTR.QC,           // A2
                 ADDR_CTR.QD,           // A3
                 RWQ_FF.Q,              // RWQ
                 HI)                    // DI

    PARAM(U_RAM.BAD_ADDR, 5)
    PARAM(U_RAM.MODE,     2)            // STUCK_LO

    ALIAS(DO, U_RAM.DO)
}
```
A complete worked example lives at
`tests/netlist/centiped/ram_region.cpp`.
## Verification
The test netlist runs through nltool with these expectations:
```
nltool --cmd=run --time_to_run=0.0001 \
       -l DO -D BAD_RAM_CELL_MODE=0 \
       tests/netlist/centiped/ram_region.cpp
```
- `BAD_RAM_CELL_MODE=0` (NORMAL): DO warms up and settles HIGH for the
  rest of the run (6 transitions in 100 µs, all during warm-up).
- `BAD_RAM_CELL_MODE=2 -D BAD_RAM_CELL_BAD_ADDR=5`: DO dips LOW for
  one address cycle (~0.5 µs at 2 MHz / 16 = 125 kHz wrap rate) every
  full sweep through the 16 cells. 32 transitions in 100 µs, exact 8 µs
  spacing.
## Implementation notes
The handler is a single `NETLIB_HANDLERI(inputs)` triggered on changes
to any of CEQ, A0..A3, RWQ, DI:
1. If CEQ is high, return early (chip not selected; DO holds).
2. Pack A0..A3 into a 4-bit address.
3. If RWQ is low and the cell isn't faulted, latch DI into the storage
   array. Faulted cells silently drop the write (a real defective cell
   can't be reprogrammed).
4. Read the storage element; substitute the fault-injected value
   (0/1/inverted) when the address matches BAD_ADDR.
5. `m_DO.push(out, 250 ns)` drives the output with a 2114-ish access delay.
The 250 ns access delay is hard-coded as `ACCESS_DELAY` in the source;
it can be revisited per Centipede-specific RAM model when the device is
widened to 1024 × 4.
## Limitations and roadmap
- **16 cells × 1 bit only.** The full Centipede working RAM region is
  1024 × 4. A future revision either widens `NUM_CELLS` and `m_A`, or
  instantiates four BAD_RAM_CELLs (one per data bit) on a shared
  address bus.
- **Single bad cell.** Only one address can be marked faulty. Multiple
  bad cells require multiple instances or a `param_array_t` of
  `BAD_ADDR` values.
- **Write rejection only.** Real RAM decay can also produce slow-write
  cells (writes succeed but flip back over milliseconds). Not modeled.
- **Single-bit fault modes.** Each fault is binary (stuck/normal). Real
  cells can have temperature-dependent or refresh-dependent
  intermittents. Out of scope for v1.
## See also
- `docs/devices/fault_buffer.md` — pin-level fault primitive (the right
  tool for clocks, address bits, and single-line shorts).
- `wiki/Phases/Phase-5.5-RAM-Region.md` — the phase deliverable, with
  test results and architecture diagrams.
- `vendor/mame/src/lib/netlist/devices/nld_2102a.cpp` — the storage
  pattern (`state_container<std::array<uint8_t, N>>`) we follow.
## References
- Project plan: `arcade_cabinet_fault_simulator_plan.md` § Component 1
- Phase 5 deferred list: `wiki/Phases/Phase-5-Address-Decoder-RAM.md`
- Test netlist: `tests/netlist/centiped/ram_region.cpp`
