// license:CC0-1.0
// Arcade Cabinet Fault Simulator — Phase 2 deliverable
//
// Centipede sync generator — REPRESENTATIVE, NOT SCHEMATIC-FAITHFUL.
//
// Phase 2 of the project plan calls for transcribing the sync generator
// from sheets 4-5 of the Atari TM-179 service manual. We don't have
// TM-179 in `docs/centipede/` yet, so this file implements the same
// architecture (chained 74161 counters + NAND-gate sync decode) at the
// real Centipede master clock rate (12.096 MHz). It produces HSYNC and
// VSYNC pulses at the right *kind* of rates, but the exact decode
// boundaries and counter widths are simplified for tractability.
//
// Once TM-179 is on hand, this file should be replaced with a
// schematic-faithful version. The instrumentation, fault-injection, and
// verification harness on top of it will all carry over unchanged.
//
// Architecture:
//
//   12.096 MHz master clock  ──► H_LO 74161 (4 bits, free-running)
//                                    │ RC (carry out, 1 of 16 cycles)
//                                    ▼
//                                H_HI 74161 (4 bits, sync-clocked)
//                                    │ RC (1 of 256 cycles)
//                                    ▼
//                                V_LO 74161 (4 bits, sync-clocked)
//                                    │ QC, QD
//                                    ▼
//   HSYNC_n  ◄── NAND(H_HI.QD, H_HI.QC, H_HI.QB)   active-low when H ≥ 224
//   VSYNC_n  ◄── NAND(V_LO.QD, V_LO.QC)            active-low when V ≥ 12
//
// Expected pulse rates at 12.096 MHz clock:
//   HSYNC period:    256 cycles  ≈ 21.16 µs   →  47.25 kHz
//   HSYNC width:      32 cycles  ≈  2.65 µs   (12.5 % duty)
//   Frame  period:  4096 cycles  ≈ 339 µs     →   2.95 kHz
//   VSYNC width:    1024 cycles  ≈  84.7 µs   (25 % duty)
//
// (The real Centipede VSYNC rate is 60 Hz; this demo wraps about 50× faster
//  to keep nltool simulation runs short. The architectural pattern is the
//  same — wider counters scale up trivially.)
//
// Run with the FAULT_BUFFER device built in:
//   nltool --cmd=run --time_to_run=0.001 \
//          -l HSYNC_n -l VSYNC_n \
//          tests/netlist/centiped/sync_generator.cpp

#include "netlist/devices/net_lib.h"

NETLIST_START(main)
{
	SOLVER(Solver, 48000)

	ANALOG_INPUT(VCC, 5.0)

	// Logic-level constants for the static counter inputs (parallel-load
	// data, CLR, LOAD). Avoids tying logic pins straight to analog rails.
	TTL_INPUT(HI, 1)
	TTL_INPUT(LO, 0)
	NET_C(VCC, HI.VCC, LO.VCC)
	NET_C(GND, HI.GND, LO.GND)

	// Real Centipede master clock.
	MAINCLOCK(CLK, 12096000)

	// ---- Devices ----
	TTL_74161(H_LO)                 // horizontal LSB (4 bits)
	TTL_74161(H_HI)                 // horizontal MSB (4 bits)
	TTL_74161(V_LO)                 // vertical (4 bits)
	TTL_7410_NAND(HSYNC_DEC)        // 3-input NAND for HSYNC_n
	TTL_7400_NAND(VSYNC_DEC)        // 2-input NAND for VSYNC_n

	// ---- H_LO: free-running 4-bit counter ----
	NET_C(CLK.Q,  H_LO.CLK)
	NET_C(HI,     H_LO.ENP)
	NET_C(HI,     H_LO.ENT)
	NET_C(HI,     H_LO.CLRQ)
	NET_C(HI,     H_LO.LOADQ)
	NET_C(LO,     H_LO.A)
	NET_C(LO,     H_LO.B)
	NET_C(LO,     H_LO.C)
	NET_C(LO,     H_LO.D)

	// ---- H_HI: synchronously chained off H_LO.RC ----
	NET_C(CLK.Q,    H_HI.CLK)
	NET_C(H_LO.RC,  H_HI.ENP)
	NET_C(H_LO.RC,  H_HI.ENT)
	NET_C(HI,       H_HI.CLRQ)
	NET_C(HI,       H_HI.LOADQ)
	NET_C(LO,       H_HI.A)
	NET_C(LO,       H_HI.B)
	NET_C(LO,       H_HI.C)
	NET_C(LO,       H_HI.D)

	// ---- V_LO: synchronously chained off the full H wrap ----
	NET_C(CLK.Q,    V_LO.CLK)
	NET_C(H_LO.RC,  V_LO.ENP)
	NET_C(H_HI.RC,  V_LO.ENT)
	NET_C(HI,       V_LO.CLRQ)
	NET_C(HI,       V_LO.LOADQ)
	NET_C(LO,       V_LO.A)
	NET_C(LO,       V_LO.B)
	NET_C(LO,       V_LO.C)
	NET_C(LO,       V_LO.D)

	// ---- HSYNC_n decode: low when H >= 224 (H[7:5] = 111) ----
	NET_C(H_HI.QD, HSYNC_DEC.A)
	NET_C(H_HI.QC, HSYNC_DEC.B)
	NET_C(H_HI.QB, HSYNC_DEC.C)
	ALIAS(HSYNC_n, HSYNC_DEC.Q)

	// ---- VSYNC_n decode: low when V >= 12 (V[3:2] = 11) ----
	NET_C(V_LO.QD, VSYNC_DEC.A)
	NET_C(V_LO.QC, VSYNC_DEC.B)
	ALIAS(VSYNC_n, VSYNC_DEC.Q)

	// ---- Power for the 74xx devices ----
	NET_C(VCC, H_LO.VCC, H_HI.VCC, V_LO.VCC, HSYNC_DEC.VCC, VSYNC_DEC.VCC)
	NET_C(GND, H_LO.GND, H_HI.GND, V_LO.GND, HSYNC_DEC.GND, VSYNC_DEC.GND)

	// (Several counter outputs are intentionally left dangling; nltool emits
	// non-fatal INFO messages for these. They're harmless.)
}
