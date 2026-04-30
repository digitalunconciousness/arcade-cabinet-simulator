# FAULT_BUFFER
Runtime fault-injection buffer for the MAME netlist solver.
Source: `vendor/mame/src/lib/netlist/devices/nld_fault_buffer.cpp`
Build registration: `vendor/mame/scripts/src/netlist.lua`,
`vendor/mame/src/lib/netlist/generated/lib_entries.hxx`,
`vendor/mame/src/lib/netlist/generated/nld_devinc.h`
## Purpose
A transparent buffer that, by default, passes its input straight through to
its output. A runtime parameter (`MODE`) lets us simulate the four primary
digital fault primitives the Arcade Cabinet Fault Simulator project relies
on: stuck-at-1, stuck-at-0, open pin, and pass-through.
The auto-instrumentation preprocessor inserts one `FAULT_BUFFER` on every
fault-eligible net pin in the Centipede PCB netlist, so the user can pick
any pin from the schematic / PCB-photo UI and inject a fault by toggling
the `MODE` parameter.
Pass-through default keeps solver overhead minimal — the buffer only
diverges from a 1 ns wire when a fault is actively armed.
## Modes
| MODE | Name      | Behavior                                                        |
|------|-----------|-----------------------------------------------------------------|
| 0    | NORMAL    | Y follows A (1 ns prop delay, default).                         |
| 1    | STUCK_HI  | Y is driven logic-high regardless of A.                         |
| 2    | STUCK_LO  | Y is driven logic-low regardless of A.                          |
| 3    | OPEN      | Y is high-impedance — pin appears physically disconnected.      |
Any value outside 0–3 is treated as NORMAL to avoid silent breakage.
## Pin map
- `A`   — logic input (the buffered signal).
- `Y`   — tristate output (drives the destination net).
- `VCC` — power, auto-connected (`@VCC` in the device declaration).
- `GND` — ground, auto-connected (`@GND` in the device declaration).
Because power is auto-connected, **do not** add `FB.GND` or `FB.VCC` to your
own `NET_C(GND, ...)` / `NET_C(VCC, ...)` lines. Doing so will trigger a
fatal `Input FB.GND already connected` error at netlist load time.
## Parameters
- `MODE` (`param_int_t`, default `0`) — the runtime fault mode (see table above).
- `FORCE_TRISTATE_LOGIC` (`param_logic_t`, default `1`) — when `1`, Y is
  treated as a logic output and OPEN mode collapses to logic-low. When `0`,
  Y is a true analog tristate node, so OPEN mode produces real high-Z that
  external pull-ups / pull-downs resolve. Set to `0` whenever the
  surrounding net is analog or you want to model the OPEN mode honestly.
## Switching delays
The current implementation hard-codes typical 74xx-buffer figures, defined
as `static constexpr` in the source:
```
TS_OFF_ON = 11 ns
TS_ON_OFF = 13 ns
SIG_DELAY =  1 ns
```
These are tunable per-instrumented-pin in a future revision; for Phase 1
the same delays are used everywhere.
## Usage in a netlist
Direct use:
```cpp
#include "netlist/devices/net_lib.h"
NETLIST_START(main)
{
    SOLVER(Solver, 48000)
    ANALOG_INPUT(VCC, 5.0)
    CLOCK(CLK1, 1000)
    FAULT_BUFFER(FB1, CLK1.Q)            // A is the second arg
    PARAM(FB1.MODE, 0)                   // 0=NORMAL  1=STUCK_HI  2=STUCK_LO  3=OPEN
    PARAM(FB1.FORCE_TRISTATE_LOGIC, 0)   // 0 = real tristate, 1 = logic-only
    RES(RL, 1000)
    NET_C(FB1.Y, RL.1)
    NET_C(GND, RL.2, CLK1.GND)           // FB1.GND auto-connects, do not list it
    NET_C(VCC,       CLK1.VCC)
}
```
Auto-instrumentation use (the typical case):
The preprocessor at `tools/preprocessor/instrument.py` walks an existing
netlist `.cpp` and inserts a `FAULT_BUFFER` on every two-pin `NET_C(...)`,
emitting a JSON manifest mapping `(refdes, pin) -> fault device name`.
See `tools/preprocessor/README.md` for invocation.
## Verification
The Phase 1 test netlist `tests/netlist/fault_buffer_test.cpp` runs the
device through all four modes via:
```
nltool --cmd=run --time_to_run=0.005 -l FB1.Y \
       -D FAULT_MODE=N tests/netlist/fault_buffer_test.cpp
```
Expected results (1 kHz clock, RL = 1 kΩ pull-down):
- `FAULT_MODE=0` (NORMAL):   Y oscillates 0.1 V ↔ 3.5 V at 1 kHz.
- `FAULT_MODE=1` (STUCK_HI): Y latches to ~3.5 V after startup.
- `FAULT_MODE=2` (STUCK_LO): Y latches to ~0.1 V.
- `FAULT_MODE=3` (OPEN):     Y collapses to ~5 µV — pulled to GND through RL.
## Implementation notes
The device is a thin wrapper around netlist's `tristate_output_t`. The
update path:
1. `NETLIB_HANDLERI(input_changed)` is invoked when A toggles.
2. `NETLIB_UPDATE_PARAMI()` is invoked at startup and any time `MODE` changes.
3. Both call `drive_output()`, which switches on `m_mode()` and either
   `m_Y.push(...)` (drive a value) or `m_Y.set_tristate(true, ...)` (high-Z).
The `tristate_output_t` template is reused from MAME's existing pattern in
`nld_74125.cpp`. We deliberately avoided introducing a new output type so
that nothing in the netlist solver needs to know about FAULT_BUFFER.
## Limitations and roadmap
- Only digital faults — analog effects (resistive shorts, leakage, slow
  edges, temperature-dependent intermittents) are deferred to v2 per the
  project plan.
- Pin-to-pin shorts are NOT handled by this device. A separate
  `FAULT_SHORT` two-terminal device is planned for Phase 1.5.
- Switching delays are global; per-pin tuning will arrive when the
  preprocessor manifest grows a `delays` field.
- Logic-mode (`FORCE_TRISTATE_LOGIC=1`) collapses OPEN to logic-low because
  the netlist solver's logic plane has no "floating" state. Use analog
  mode for honest OPEN-pin behavior.
## See also
- `docs/devices/bad_ram_cell.md` — cell-level fault primitive (the
  right tool for single-cell RAM decay symptoms; FAULT_BUFFER on a
  RAM data line would fault every address, not just one).
- `wiki/Phases/Phase-5.5-RAM-Region.md` — the BAD_RAM_CELL phase
  deliverable, with test results and architecture diagrams.
## References
- Project plan: `arcade_cabinet_fault_simulator_plan.md` § Component 1
- Netlist conventions reference: `vendor/mame/src/lib/netlist/devices/nld_74125.cpp`
- Build registration walkthrough: this commit's diff
