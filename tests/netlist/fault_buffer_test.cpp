// license:CC0-1.0
// Arcade Cabinet Fault Simulator — Phase 1 unit test
//
// Drives a 1 kHz clock through FAULT_BUFFER and logs the buffered output.
// Use -DFAULT_MODE=0|1|2|3 to sweep through fault modes:
//   0 = NORMAL    (Y follows A)
//   1 = STUCK_HI  (Y always 1)
//   2 = STUCK_LO  (Y always 0)
//   3 = OPEN      (Y high-impedance; pulled to GND through RL)
//
// Run, for each mode:
//   nltool --cmd=run --time_to_run=0.005 -l FB1.Y \
//       -D FAULT_MODE=0 tests/netlist/fault_buffer_test.cpp
//
// Output is a CSV of (time, Y) you can plot or grep.

#include "netlist/devices/net_lib.h"

#ifndef FAULT_MODE
#define FAULT_MODE 0
#endif

NETLIST_START(main)
{
	SOLVER(Solver, 48000)

	ANALOG_INPUT(VCC, 5.0)

	CLOCK(CLK1, 1000)                       // 1 kHz square wave on CLK1.Q
	FAULT_BUFFER(FB1, CLK1.Q)
	PARAM(FB1.MODE, FAULT_MODE)             // overridden via -D FAULT_MODE=N
	PARAM(FB1.FORCE_TRISTATE_LOGIC, 0)      // analog tri-state so OPEN floats

	// Pull-down so OPEN mode resolves to a definite low instead of floating.
	RES(RL, 1000)
	NET_C(FB1.Y, RL.1)

	// FB1.VCC and FB1.GND auto-connect because of FAULT_BUFFER's @VCC,@GND.
	NET_C(GND, RL.2, CLK1.GND)
	NET_C(VCC,       CLK1.VCC)
}
