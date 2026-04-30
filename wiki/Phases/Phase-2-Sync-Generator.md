# Phase 2 — Sync generator netlist coverage
**Status:** ✅ complete (representative; schematic-faithful pass deferred)
**Goal:** Netlist the Centipede sync generator (sheets 4–5 of the
schematic — pure TTL counter chain producing HSYNC, VSYNC, and timing
signals built from 74161s and a few 74xx gates). Demonstrate one
end-to-end PCB fault with visible symptoms (rolling picture, torn frames,
or missing video).
**Estimate:** 3–4 weekends. **Actual: 1 evening (representative pass).**
## Current state of schematic integration
**The Phase 2 deliverable is end-to-end working as a *representative*
netlist**, not a schematic-faithful one. Here's where each piece stands:
- TM-182 service manual (1st and 6th printings) and DP-182 schematics
  (4 PDFs, sheets 01A/01B/02A/02B) are downloaded into
  `docs/centipede/` from public arcade-preservation archives. Sourced
  per repo policy in [References](../References.md); not redistributed
  via this repo.
- The DP-182 PDFs are single-page raster scans at ~2400×1600 pt with
  no text layer. `pdftotext` extracts nothing; programmatic
  schematic-to-netlist transcription is not feasible from these scans.
- `tests/netlist/centiped/sync_generator.cpp` therefore remains the
  *representative* netlist (chained 74161 counters + NAND-gate sync
  decode at the real 12.096 MHz master clock, simplified counter widths
  and decode boundaries). All Phase 2 deliverables built on top of it
  — the instrumented netlist, the manifest, the fault scenario — work
  as designed.
- The path to schematic-faithful: a human reads the relevant DP-182
  sheets and either edits `sync_generator.cpp` directly with the real
  reference designators and net names, or shares snipped sheet sections
  as images for joint interpretation. The abstraction boundary at the
  netlist file means the instrumentation, manifest, fault scenarios,
  and Phase 3 UI all carry over unchanged — only `sync_generator.cpp`
  itself needs to change.
## What landed
- `tests/netlist/centiped/sync_generator.cpp` — the base netlist:
  `H_LO`, `H_HI` (8-bit synchronous H counter chain), `V_LO` (4-bit V
  counter), and 7400/7410 NAND gates decoding `HSYNC_n` and `VSYNC_n`.
- `build/instrumented/sync_generator.cpp` — preprocessor output with
  one `FAULT_BUFFER` per fault-eligible 2-pin connection.
- `build/instrumented/sync_generator.manifest.json` — 8 instrumented
  pins: `CLK.Q`, `H_LO.RC`, `H_HI.RC`, `H_HI.QB/QC/QD`, `V_LO.QC/QD`.
- `tests/netlist/centiped/scenarios/fault_vsync_qc_stuck_lo.cpp` — a
  fault scenario that holds `FB_V_LO_QC` in STUCK_LO. VSYNC_n then
  never asserts — the rolling-picture symptom we wanted to reproduce.
## Verification commands
```bash
# 1. Bare netlist runs and produces HSYNC/VSYNC at the expected rates.
./vendor/mame/nltool --cmd=run --time_to_run=0.001 \
    -l HSYNC_n -l VSYNC_n \
    tests/netlist/centiped/sync_generator.cpp
wc -l log_HSYNC_n.log log_VSYNC_n.log
#  98 log_HSYNC_n.log    → ~49 kHz HSYNC (expected 47.25 kHz)
#   9 log_VSYNC_n.log    →  ~3 kHz VSYNC + startup (expected 2.95 kHz)
# 2. Run the preprocessor.
source .venv/bin/activate
python tools/preprocessor/instrument.py \
    --input  tests/netlist/centiped/sync_generator.cpp \
    --output build/instrumented/sync_generator.cpp \
    --manifest build/instrumented/sync_generator.manifest.json
# instrumented 8 pins
# 3. Instrumented netlist matches base in NORMAL mode (all FAULT_BUFFERs idle).
./vendor/mame/nltool --cmd=run --time_to_run=0.001 \
    -l HSYNC_n -l VSYNC_n \
    build/instrumented/sync_generator.cpp
wc -l log_HSYNC_n.log log_VSYNC_n.log
#  98 log_HSYNC_n.log
#   9 log_VSYNC_n.log     ← identical to base
# 4. Stick FB_V_LO_QC low and observe VSYNC stop firing.
./vendor/mame/nltool --cmd=run --time_to_run=0.001 \
    -l HSYNC_n -l VSYNC_n \
    tests/netlist/centiped/scenarios/fault_vsync_qc_stuck_lo.cpp
wc -l log_HSYNC_n.log log_VSYNC_n.log
#  98 log_HSYNC_n.log     ← unchanged — fault is localized
#   4 log_VSYNC_n.log     ← only startup transients; VSYNC_n then latched high
```
## Architecture (representative)
```
12.096 MHz master  ──► H_LO 74161 (4 bits, free-running)
                          │ RC
                          ▼
                       H_HI 74161 (4 bits, sync-clocked off H_LO.RC)
                          │ RC
                          ▼
                       V_LO 74161 (4 bits, sync-clocked off H_HI.RC)
HSYNC_n  ◄── NAND(H_HI.QD, H_HI.QC, H_HI.QB)   active-low when H ≥ 224
VSYNC_n  ◄── NAND(V_LO.QD, V_LO.QC)            active-low when V ≥ 12
```
This intentionally wraps faster than real Centipede so an nltool run of
1 ms produces several frames worth of behavior. Counter widths scale up
trivially when we transcribe the real schematic.
## Gotchas
- TTL devices declared with no inline args (`TTL_74161(H_LO)`) do NOT
  get auto-power. Wire `VCC` and `GND` explicitly via `NET_C`.
- `NC_PIN` is for genuinely-unused inputs. Connecting an unused output
  to it triggers a fatal error. Just leave outputs dangling; nltool
  emits an INFO-level warning that's non-fatal.
- Multi-driver `NET_C` lines (e.g. `NET_C(VCC, A.VCC, B.VCC, C.VCC)`)
  are correctly skipped by the Phase-1 preprocessor; only 2-pin
  connections become fault-injection targets, which is what we want
  for power and global control nets.
- The 4-bit V counter only gives us 16 V values, so the VSYNC decode
  threshold (V ≥ 12) gives a 25 % duty cycle. That's much wider than
  real Centipede VSYNC; widen the V counter to 9 bits when going
  schematic-faithful.
## Out of scope for this phase (deferred)
- Schematic-faithful counter widths (real Centipede uses 9-bit V and
  ~9-bit H with non-trivial decode of HSYNC and HBLANK).
- Hooking the netlist up to MAME's centiped driver so faults manifest
  on the actual game's video output. This needs the cabinet bus from
  Phase 3 to be in place first.
- `FAULT_SHORT` injection between physically-adjacent pins.
- Per-pin tunable `FAULT_BUFFER` switching delays.
## What unblocks Phase 3
- A real netlist with multiple instrumented FAULT_BUFFERs proves the
  preprocessor handles a non-trivial circuit.
- The fault-scenario file format (a copy of the instrumented netlist
  with `PARAM(FB_*.MODE, ...)` lines appended) is a viable serialization
  for the UI to drive when Phase 3 wires it up over the cabinet bus.
