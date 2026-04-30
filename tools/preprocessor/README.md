# Auto-instrumentation preprocessor
Phase 1 scaffold of the netlist auto-instrumentation tool described in
`arcade_cabinet_fault_simulator_plan.md` § Component 1 ("Auto-instrumentation").

## What it does
Reads a MAME netlist `.cpp` source file, walks its `NET_C(...)` connection
list, and rewrites simple two-pin connections to route the driving signal
through a `FAULT_BUFFER` device:

```
// before
NET_C(R1.1, U2.A)

// after
FAULT_BUFFER(FB_R1_1, R1.1)
NET_C(FB_R1_1.Y, U2.A)
```

It also emits a JSON manifest mapping `(refdes, pin) -> fault device name`
so the UI can resolve a clickable region on the schematic / PCB photo to
the runtime fault target.

## Phase 1 status (scaffold)
What's implemented:
- Recognizes simple two-pin `NET_C` connections
- Skips power rails (`GND`, `VCC`) and other bare-token names
- Optional `--include-pins` whitelist
- Emits a JSON manifest with `refdes`, `pin`, `fault_device`, `source_line`, `original_net`
- Idempotent against multiple NET_Cs sharing a driver pin
- Unit tests with `test_instrument.py`

What's NOT yet implemented (deferred to later sub-phases):
- Multi-driver (>2 pin) NET_C — these are shared buses and need different rewrite logic
- `.hxx`-style template expansions used by `nld_9316_base.hxx` etc.
- Pin-to-pin short (`FAULT_SHORT`) insertion driven by KiCad PCB layout
- Macro / DIP wrapper devices (instrumentation needs to look through them)
- Performance optimization (currently regex-per-line)

## Usage

```
source /home/jackie/arcade-sim/.venv/bin/activate

python tools/preprocessor/instrument.py \\
    --input  vendor/mame/src/lib/netlist/devices/nld_log.cpp \\
    --output build/instrumented/nld_log.cpp \\
    --manifest build/instrumented/nld_log.manifest.json
```

## Tests

```
cd /home/jackie/arcade-sim
source .venv/bin/activate
python tools/preprocessor/test_instrument.py
```
