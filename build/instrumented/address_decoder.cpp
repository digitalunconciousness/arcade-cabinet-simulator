// license:CC0-1.0
// Arcade Cabinet Fault Simulator — Phase 5 deliverable
//
// Centipede address decoder — REPRESENTATIVE, NOT SCHEMATIC-FAITHFUL.
//
// Phase 5 calls for transcribing sheet 2 of TM-182/DP-182, which is
// where Centipede decodes high-order address bits (with /MEM_R, /MEM_W)
// into chip-select signals for the ROM, RAM, POKEY, EAROM, and video
// RAM. The schematic PDFs are raster scans (see Phase 2 notes), so
// like the sync generator this file delivers a *representative*
// implementation with the same architectural shape:
//
//   - A 74161 counter stands in for the CPU's bus address driver. Its
//     low two output bits walk 0..3 every four clocks, mimicking how
//     the CPU sweeps through different address regions during a frame.
//   - A 74155A half-decoder (TTL_74155A_GATE) takes those two address
//     bits plus an active-low enable and asserts exactly one of four
//     active-low chip-select lines. (We'd prefer 74139 here, but its
//     truth-table timing array is malformed in MAME 0.287 — 4 outputs
//     but only 1 timing value, which trips the parser. 74155A has the
//     same demux semantics with a correctly-formed timing array.)
//
// The four chip-select lines are aliased ROM_CSn, RAM_CSn, POKEY_CSn,
// EAROM_CSn — names that match the real Centipede design's chip-select
// fan-out, even though the address widths are simplified for
// tractability. Once TM-182 sheet 2 is read in human-readable form the
// counter widens to A12..A15 and the decoder becomes a pair of 74139
// halves (decoder + qualifying 74138).
//
// Run with the FAULT_BUFFER device in the netlist library:
//
//   nltool --cmd=run --time_to_run=0.0002 \
//          -l ROM_CSn -l RAM_CSn -l POKEY_CSn -l EAROM_CSn \
//          tests/netlist/centiped/address_decoder.cpp
//
// At a 1 MHz bus clock the counter wraps 0..3 in 4 µs, so a 200 µs run
// produces ~50 wraps and each chip-select asserts ~50 times.

#include "netlist/devices/net_lib.h"

NETLIST_START(main)
{
	SOLVER(Solver, 48000)

	ANALOG_INPUT(VCC, 5.0)

	TTL_INPUT(HI, 1)
	TTL_INPUT(LO, 0)
	NET_C(VCC, HI.VCC, LO.VCC)
	NET_C(GND, HI.GND, LO.GND)

	// 1 MHz stand-in for the 6502's bus rate (real Centipede 6502 runs
	// at 1.512 MHz; round-numbered for predictable verification).
	MAINCLOCK(CLK, 1000000)

	// ---- Devices ----
	TTL_74161(ADDR_CTR)         // 4-bit counter; we use QA/QB as A0/A1
	TTL_74155A_GATE(DEC)        // 2-to-4 active-low demux

	// ---- ADDR_CTR: free-running counter, low 2 bits drive the decoder ----
	FAULT_BUFFER(FB_CLK_Q, CLK.Q)
	NET_C(FB_CLK_Q.Y, ADDR_CTR.CLK)
	NET_C(HI,     ADDR_CTR.ENP)
	NET_C(HI,     ADDR_CTR.ENT)
	NET_C(HI,     ADDR_CTR.CLRQ)
	NET_C(HI,     ADDR_CTR.LOADQ)
	NET_C(LO,     ADDR_CTR.A)
	NET_C(LO,     ADDR_CTR.B)
	NET_C(LO,     ADDR_CTR.C)
	NET_C(LO,     ADDR_CTR.D)

	// ---- 74155A decoder ----
	// Pin map: B,A = address bits (B is MSB), G = active-low enable,
	// C = data input (tie high so the demux outputs active-low CS).
	NET_C(LO,          DEC.G)   // enable held low
	NET_C(HI,          DEC.C)   // data tied high
	FAULT_BUFFER(FB_ADDR_CTR_QA, ADDR_CTR.QA)
	NET_C(FB_ADDR_CTR_QA.Y, DEC.A)
	FAULT_BUFFER(FB_ADDR_CTR_QB, ADDR_CTR.QB)
	NET_C(FB_ADDR_CTR_QB.Y, DEC.B)

	// Chip-select aliases. Each is active-low. 74155A names the outputs
	// Y0..Y3; we re-alias them to chip-select-flavored names.
	ALIAS(ROM_CSn,   DEC.Y0)
	ALIAS(RAM_CSn,   DEC.Y1)
	ALIAS(POKEY_CSn, DEC.Y2)
	ALIAS(EAROM_CSn, DEC.Y3)

	// Power
	NET_C(VCC, ADDR_CTR.VCC, DEC.VCC)
	NET_C(GND, ADDR_CTR.GND, DEC.GND)

	// Counter has spare outputs (QC, QD, RC) that we don't use; nltool
	// emits non-fatal INFO messages for those, same as Phase 2.
}
