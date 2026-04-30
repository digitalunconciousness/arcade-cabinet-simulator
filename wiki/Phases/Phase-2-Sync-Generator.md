# Phase 2 — Sync generator netlist coverage
**Status:** 🚧 not started
**Goal:** Netlist the Centipede sync generator (sheets 4–5 of the
schematic — pure TTL counter chain producing HSYNC, VSYNC, and timing
signals built from 74161s and a few 74xx gates). Demonstrate one
end-to-end PCB fault with visible symptoms (rolling picture, torn frames,
or missing video).
**Estimate:** 3–4 weekends per the project plan.
## Why this target first
- Pure TTL — no Atari custom chips, no LSI to reverse-engineer.
- Faults produce visually obvious symptoms, perfect for the first demo.
- Self-contained on the schematic, easy to bound the netlist scope.
- Builds confidence in the full toolchain (instrumentation preprocessor +
  fault buffer + MAME integration) on something tractable.
## Plan sketch
1. Transcribe the sync generator from the TM-179 schematic into a
   handwritten netlist `.cpp` under `tests/netlist/centiped/`. Connect it
   to a logic-input clock for now; the full PCB-clock integration comes
   later.
2. Verify the bare netlist with nltool — pulses on HSYNC/VSYNC at the
   expected rates.
3. Run the auto-instrumentation preprocessor across it. Confirm every
   instrumented pin appears in the manifest JSON.
4. Build a tiny harness (Lua plugin or small C++ wrapper) that lets us
   flip a `FAULT_BUFFER` MODE at runtime and verify the symptom.
5. Pick one fault — likely a stuck VSYNC line — and capture before/after
   waveforms in the wiki.
## Open questions
- Hand-write the netlist or run KiCad → MAME via `mamedev/discrete`?
  Hand-writing is faster for one sub-circuit; the bridge becomes
  worthwhile once we tackle the address decoder + RAM region.
- Where does the sync generator's master clock come from in our
  simulation? Real Centipede uses a 12.096 MHz crystal with division;
  for the standalone netlist a `MAINCLOCK` is sufficient.
## Deliverables to land in the same commit as the phase
- The netlist source.
- The instrumented netlist + manifest JSON committed under
  `build/instrumented/` (or wherever the preprocessor outputs end up).
- Updated `Phase-2-Sync-Generator.md` (status, gotchas, verification).
- Updated `Home.md` and `Roadmap.md` (status pointers).
- New ADR if any non-trivial architectural calls fall out of this work.
