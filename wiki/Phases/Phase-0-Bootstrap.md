# Phase 0 — Bootstrap
**Status:** ✅ complete
**Goal:** Build MAME from source, run Centipede, get comfortable with the
netlist runtime.
## What landed
- Project workspace at `/home/jackie/arcade-sim/`.
- Upstream MAME (master at `0.287`) shallow-cloned to `vendor/mame/`.
- MAME-KiCad bridge (`mamedev/discrete`) cloned to `vendor/discrete/`.
- Python venv at `.venv/` with `pyparsing`, `lark`, `jsonschema`.
- MAME built with `SOURCES=src/mame/atari/centiped.cpp` so the binary
  contains only the Centipede driver and dependencies (~10 minute build,
  72 MB binary).
- Centipede revision 3 ROM set verified by `mame -verifyroms centiped3`.
- Headless smoke test (`mame -bench 10 centiped3`) hits ~1300% real time.
## Gotchas
- `centiped.zip` shipped as the rev-3 set; in MAME 0.287 the `centiped`
  parent is rev-4. Run as `centiped3` instead, or rename the zip.
- MAME 0.287 has a new audio system. `-sound auto` is silent by default;
  use `-sound pipewire` (or `pulse`) explicitly. See [Build-Notes](../Build-Notes.md).
- `SOURCES=...centiped.cpp` is great for fast iteration on the emulator
  but does NOT compile the netlist library, because Centipede doesn't use
  netlist devices. To build `nltool` and the netlist library we have to
  add `TOOLS=1` and the build will then expand to the full netlist
  toolchain. See [Phase 1](Phase-1-Fault-Buffer.md).
- The `git describe` "fatal: No names found" line during `make` is a
  benign side-effect of the shallow clone. Ignore it.
## Verification commands
```bash
cd vendor/mame
./mame -version                                # 0.287 (unknown)
./mame -rompath ../../roms -verifyroms centiped3
./mame -rompath ../../roms -bench 10 centiped3 # ~13× real time
./mame -rompath ../../roms -window -sound pipewire centiped3
```
