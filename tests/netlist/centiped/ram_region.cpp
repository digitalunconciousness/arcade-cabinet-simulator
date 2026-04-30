// license:CC0-1.0
// Arcade Cabinet Fault Simulator — Phase 5.5 deliverable
//
// RAM region with cell-level fault modeling. This netlist exercises
// the new BAD_RAM_CELL device by walking a 4-bit address counter
// across all 16 cells, writing the data line high on every cycle and
// reading back on the next.
//
// In NORMAL mode (MODE=0) every cell stores and returns the value
// that was written, so DO is high after the first full sweep. With a
// stuck-at fault on a single cell (MODE=2 STUCK_LO at BAD_ADDR=5),
// every other address still reads back high but address 5 returns 0
// — proving the device isolates faults to one cell rather than
// poisoning the whole region.
//
// Run with:
//
//   nltool --cmd=run --time_to_run=0.0002 \
//          -l ADDR_QA -l ADDR_QB -l ADDR_QC -l ADDR_QD -l DO -l RWQ \
//          -D BAD_RAM_CELL_MODE=0 \
//          tests/netlist/centiped/ram_region.cpp
//
// The instrumentation harness (Flask UI) flips MODE between 0 and 2
// to demonstrate a single-cell stuck-at fault.
//
// Address counter: 1 MHz / 16 = 62.5 kHz wrap. RWQ is driven directly
// from the LSB of a divide-by-2 latch so that every cell sees one
// write cycle followed by one read cycle.

#include "netlist/devices/net_lib.h"

#ifndef BAD_RAM_CELL_BAD_ADDR
#define BAD_RAM_CELL_BAD_ADDR 5
#endif

#ifndef BAD_RAM_CELL_MODE
#define BAD_RAM_CELL_MODE 0  // 0=NORMAL, 1=STUCK_HI, 2=STUCK_LO, 3=FLIP
#endif

NETLIST_START(main)
{
	SOLVER(Solver, 48000)

	ANALOG_INPUT(VCC, 5.0)

	TTL_INPUT(HI, 1)
	TTL_INPUT(LO, 0)
	NET_C(VCC, HI.VCC, LO.VCC)
	NET_C(GND, HI.GND, LO.GND)

	// 2 MHz drive — every cell gets a write cycle then a read cycle
	// at the address-counter rate of 1 MHz (clock divided by 2).
	MAINCLOCK(CLK, 2000000)

	// ---- Address counter: 4-bit, walks 0..15 ----
	TTL_74161(ADDR_CTR)
	NET_C(CLK.Q,  ADDR_CTR.CLK)
	NET_C(HI,     ADDR_CTR.ENP)
	NET_C(HI,     ADDR_CTR.ENT)
	NET_C(HI,     ADDR_CTR.CLRQ)
	NET_C(HI,     ADDR_CTR.LOADQ)
	NET_C(LO,     ADDR_CTR.A)
	NET_C(LO,     ADDR_CTR.B)
	NET_C(LO,     ADDR_CTR.C)
	NET_C(LO,     ADDR_CTR.D)
	NET_C(VCC,    ADDR_CTR.VCC)
	NET_C(GND,    ADDR_CTR.GND)

	// Surface address-counter taps for logging.
	ALIAS(ADDR_QA, ADDR_CTR.QA)
	ALIAS(ADDR_QB, ADDR_CTR.QB)
	ALIAS(ADDR_QC, ADDR_CTR.QC)
	ALIAS(ADDR_QD, ADDR_CTR.QD)

	// ---- RWQ generator: divide CLK by 2 with a 7474 D-flop ----
	// QQ wired back to D gives us a toggling RWQ that is low (write)
	// for one address cycle and high (read) for the next, so each
	// cell gets a write cycle and a separate read cycle while the
	// address increments on the falling edge of the slower phase.
	TTL_7474(RWQ_FF)
	NET_C(CLK.Q,    RWQ_FF.CLK)
	NET_C(RWQ_FF.QQ, RWQ_FF.D)
	NET_C(HI,       RWQ_FF.CLRQ)
	NET_C(HI,       RWQ_FF.PREQ)
	NET_C(VCC,      RWQ_FF.VCC)
	NET_C(GND,      RWQ_FF.GND)
	ALIAS(RWQ, RWQ_FF.Q)

	// ---- BAD_RAM_CELL: 16 cells, fault-injectable ----
	BAD_RAM_CELL(U_RAM,
	             /*CEQ*/ LO,                // chip always selected
	             /*A0*/  ADDR_CTR.QA,
	             /*A1*/  ADDR_CTR.QB,
	             /*A2*/  ADDR_CTR.QC,
	             /*A3*/  ADDR_CTR.QD,
	             /*RWQ*/ RWQ_FF.Q,
	             /*DI*/  HI)                // always write 1s
	// VCC/GND are auto-connected via the @VCC,@GND defaults in the
	// device's NETLIB_DEVICE_IMPL macro.

	PARAM(U_RAM.BAD_ADDR, BAD_RAM_CELL_BAD_ADDR)
	PARAM(U_RAM.MODE,     BAD_RAM_CELL_MODE)

	ALIAS(DO, U_RAM.DO)
}
