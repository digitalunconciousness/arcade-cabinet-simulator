# Arcade Cabinet Fault Simulator
Workspace for the project described in `arcade_cabinet_fault_simulator_plan.md`.
Goal: simulate an entire Centipede cabinet (PCB + power supply + monitor +
trackball + coin mech + harness + lights + audio) and let a user inject
realistic faults at any subsystem. Phase 1 is complete — fault-injection
plumbing in the MAME netlist solver works end-to-end on a trivial netlist.
## Layout (tracked)
- `arcade_cabinet_fault_simulator_plan.md` — master plan / source of truth.
- `patches/` — patch series we keep on top of upstream MAME. See
  `patches/README.md` for how to apply.
- `tools/preprocessor/` — Python auto-instrumentation tool that walks a
  netlist `.cpp` and inserts `FAULT_BUFFER` on every fault-eligible pin,
  emitting a JSON manifest the UI consumes.
- `tests/netlist/` — nltool harness netlists used to verify the
  fault-injection devices.
- `docs/devices/` — documentation for the netlist devices we add to MAME.
- `ui/` — placeholder for the future UI app (web/Electron, TBD).
## Layout (untracked, gitignored)
- `vendor/mame/` — upstream MAME shallow clone. Apply
  `patches/*.patch` after cloning to reproduce our additions.
- `vendor/discrete/` — MAME-KiCad bridge (`mamedev/discrete`).
- `roms/` — local ROM set; legal sourcing required, never committed.
- `docs/{centipede,wells-gardner,cojag}/` — service manuals (PDFs).
- `scans/centipede/` — Sean Riddle PCB scans + our freshly-refit board scans.
- `scratch/` — throwaway experiments.
- `.venv/` — Python venv (`pyparsing`, `lark`, `jsonschema` installed).
## Bootstrapping a fresh checkout
```bash
# 1. Clone the workspace.
git clone <this repo> arcade-sim && cd arcade-sim
# 2. Pull MAME and apply our patch series.
git clone --depth=1 https://github.com/mamedev/mame.git vendor/mame
( cd vendor/mame && git am ../../patches/*.patch )
git clone --depth=1 https://github.com/mamedev/discrete.git vendor/discrete
# 3. Python venv.
python -m venv .venv
source .venv/bin/activate
pip install pyparsing lark jsonschema
# 4. Build MAME (Centipede driver + nltool).
cd vendor/mame
make -j"$(nproc)" SOURCES=src/mame/atari/centiped.cpp TOOLS=1
# 5. Smoke-test.
./mame -rompath ../../roms -bench 5 centiped3
./nltool --cmd=run --time_to_run=0.005 -l FB1.Y \
    -D FAULT_MODE=1 ../../tests/netlist/fault_buffer_test.cpp
```
## Running MAME with audio
Use the new sound system explicitly:
```bash
./mame -rompath ../../roms -window -sound pipewire centiped3
```
## Documentation
- [`wiki/Home.md`](wiki/Home.md) — project wiki landing page; phase
  status, roadmap, devices, build notes, ADRs.
- `docs/devices/fault_buffer.md` — the FAULT_BUFFER netlist device.
- `tools/preprocessor/README.md` — auto-instrumentation preprocessor.
- `patches/README.md` — patch series workflow.
## Wiki workflow
The wiki is tracked in-repo at [`wiki/`](wiki/) so phase commits update
code and prose atomically. To publish a styled rendering to GitHub's Wiki
tab, run `tools/sync-wiki.sh` after enabling the wiki feature once via
`gh repo edit --enable-wiki`. See
[`wiki/Decisions/ADR-0001-wiki-workflow.md`](wiki/Decisions/ADR-0001-wiki-workflow.md)
for the rationale.
