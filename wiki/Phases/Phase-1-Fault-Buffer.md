# Phase 1 — Fault buffer device + preprocessor scaffold
**Status:** ✅ complete
**Goal:** Add a runtime-fault-injectable buffer to MAME's netlist library
and prove it on a trivial netlist. Scaffold the auto-instrumentation
preprocessor that will eventually wrap every Centipede pin.
## What landed
- `FAULT_BUFFER` netlist device — `vendor/mame/src/lib/netlist/devices/nld_fault_buffer.cpp`.
  - Modes: `0=NORMAL`, `1=STUCK_HI`, `2=STUCK_LO`, `3=OPEN`.
  - `tristate_output_t` so OPEN mode honestly produces high-Z that
    external pull-ups / pull-downs resolve.
  - `param_int_t MODE` is updated at runtime via `NETLIB_UPDATE_PARAMI`,
    no recompile needed to flip a fault.
- Build registration in `scripts/src/netlist.lua`,
  `src/lib/netlist/generated/lib_entries.hxx`, and
  `src/lib/netlist/generated/nld_devinc.h`. Captured as a portable patch
  in `patches/0001-Add-FAULT_BUFFER-netlist-device-for-runtime-fault-in.patch`.
- Test netlist `tests/netlist/fault_buffer_test.cpp` — drives a 1 kHz
  clock through the buffer with a 1 kΩ pull-down and logs Y for inspection.
- Auto-instrumentation preprocessor scaffold at `tools/preprocessor/`
  with CLI, JSON manifest schema, README, and 10 passing unit tests
  (`test_instrument.py`).
- Device documentation in [`docs/devices/fault_buffer.md`](../../docs/devices/fault_buffer.md)
  and a wiki mirror at [`Devices/FAULT_BUFFER.md`](../Devices/FAULT_BUFFER.md).
## Gotchas
- `@VCC,@GND` in `NETLIB_DEVICE_IMPL` auto-connects power, so explicit
  `NET_C(GND, ..., FB1.GND)` will fail with `Input FB1.GND already
  connected`. Leave power off the explicit `NET_C` lines.
- The netlist preprocessor does C-style macro expansion on bare tokens.
  `-D MODE=0` collides with `FB1.MODE`, expanding it to `FB1.0`. Use a
  scoped name like `FAULT_MODE` for any preprocessor define.
- `FORCE_TRISTATE_LOGIC=1` collapses OPEN-mode high-Z to logic-low
  because the netlist solver's logic plane has no floating state. Set to
  `0` for analog tristate behavior on any net that touches a resistor or
  other analog component.
- The `nld_devinc.h` and `lib_entries.hxx` files are nominally generated
  by `src/lib/netlist/build/create_devinc.py` and `create_lib_entries.py`,
  but they're checked in. Hand-edit when adding a single device; if you
  start adding many, regenerate them by piping all device sources through
  the python scripts.
- MAME's netlist library is only built when a driver that uses netlists is
  in `SOURCES`, OR when `TOOLS=1` is set. Centipede doesn't use netlists,
  so to verify netlist changes use:
  `make -j3 SOURCES=src/mame/atari/centiped.cpp TOOLS=1`.
## Verification commands
```bash
cd vendor/mame
make -j3 SOURCES=src/mame/atari/centiped.cpp TOOLS=1
./nltool --cmd=list-devices | grep FAULT_BUFFER
# FAULT_BUFFER         FAULT_BUFFER(<id>,+A,@VCC,@GND)
cd /home/jackie/arcade-sim
for m in 0 1 2 3; do
  ./vendor/mame/nltool --cmd=run --time_to_run=0.005 -l FB1.Y \
       -D FAULT_MODE=$m tests/netlist/fault_buffer_test.cpp
  awk 'END{print "  range:", min, "..", max} {if(NR==1||$2<min)min=$2; if($2>max)max=$2}' \
      log_FB1.Y.log
  rm -f log_FB1.Y.log
done
```
Expected (1 kΩ pull-down, FORCE_TRISTATE_LOGIC=0):
- `FAULT_MODE=0` (NORMAL):  Y oscillates 0.1 V ↔ 3.5 V at 1 kHz.
- `FAULT_MODE=1` (STUCK_HI): Y latches to ~3.5 V.
- `FAULT_MODE=2` (STUCK_LO): Y latches to ~0.1 V.
- `FAULT_MODE=3` (OPEN):     Y collapses to ~5 µV.
## Preprocessor unit tests
```bash
source .venv/bin/activate
python tools/preprocessor/test_instrument.py
# 10 tests, all PASS
```
## Out of scope for Phase 1 (deferred)
- Multi-driver / >2-pin `NET_C` rewrite — needs bus-aware logic.
- `.hxx` template expansions used by `nld_9316_base.hxx` etc.
- Pin-to-pin shorts (`FAULT_SHORT`) driven by KiCad PCB layout.
- DIP wrapper devices — preprocessor needs to look through them.
- Per-pin tunable switching delays.
## What unblocks Phase 2
- A real netlist target to instrument (the sync generator).
- The preprocessor scaffold is enough for the trivial cases that arise
  in the sync generator; bus rewriting can be deferred until the address
  decoder phase forces it.
## Navigation
← Previous: [Phase 0 — Bootstrap](Phase-0-Bootstrap.md) ·
Next: [Phase 2 — Sync generator](Phase-2-Sync-Generator.md) →
