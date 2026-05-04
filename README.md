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
pip install pyparsing lark jsonschema flask
# 4. Install Xvfb (headless X11 for the video stream).
#    Arch: sudo pacman -S xorg-server-xvfb
#    Debian/Ubuntu: sudo apt install xvfb
# 5. Build MAME (Centipede driver + nltool).
cd vendor/mame
make -j"$(nproc)" SOURCES=src/mame/atari/centiped.cpp TOOLS=1
# 6. Smoke-test.
./mame -rompath ../../roms -bench 5 centiped3
./nltool --cmd=run --time_to_run=0.005 -l FB1.Y \
    -D FAULT_MODE=1 ../../tests/netlist/fault_buffer_test.cpp
```
## Running MAME with audio
Use the new sound system explicitly:
```bash
./mame -rompath ../../roms -window -sound pipewire centiped3
```
## Demo (Phase 7 vertical-slice)

One command starts everything:

```bash
source .venv/bin/activate
pip install flask                    # if not already done
bash tools/run-demo.sh               # http://127.0.0.1:5050
```

`run-demo.sh` launches Xvfb (headless X11), MAME with the `cabinet_bus`
plugin, and the Flask UI server, then waits for the plugin socket before
printing the URL. Ctrl-C stops all three processes cleanly.

Open `http://127.0.0.1:5050`. The page shows:

- a **Centipede emulator** panel with a live MJPEG video feed of the
  running game, ROM name, frame counter, paused/running state, and
  Pause / Resume / Soft-reset buttons,
- **keyboard controls** — WASD moves the trackball, Space fires, 1
  starts 1-player, 2 starts 2-player, 5 inserts a coin,
- the **sync generator schematic** with clickable fault-injection
  pins and live HSYNC/VSYNC waveforms,
- a **scenario dropdown** — pick a named fault (e.g. "dim PSU 5V",
  "sprite RAM glitch"), click **Apply**, see the effect in the running
  game within one second.

If MAME isn't running the emulator panel shows an offline placeholder;
the schematic and fault injection still work standalone.

Full walkthroughs:
[`wiki/Phases/Phase-3-Cabinet-Bus.md`](wiki/Phases/Phase-3-Cabinet-Bus.md),
[`wiki/Phases/Phase-3.5-MAME-Bridge.md`](wiki/Phases/Phase-3.5-MAME-Bridge.md),
and
[`wiki/Phases/Phase-7-Cabinet-UI-Training.md`](wiki/Phases/Phase-7-Cabinet-UI-Training.md).
## Documentation
- [`wiki/Home.md`](wiki/Home.md) — project wiki landing page; phase
  status, roadmap, devices, build notes, ADRs.
- `docs/devices/fault_buffer.md` — the FAULT_BUFFER netlist device.
- `tools/preprocessor/README.md` — auto-instrumentation preprocessor.
- `tools/cabinet_bus/` — Phase 3 server + UI sources.
- `patches/README.md` — patch series workflow.
## Wiki workflow
The wiki is tracked in-repo at [`wiki/`](wiki/) so phase commits update
code and prose atomically. To publish a styled rendering to GitHub's Wiki
tab, run `tools/sync-wiki.sh` after enabling the wiki feature once via
`gh repo edit --enable-wiki`. See
[`wiki/Decisions/ADR-0001-wiki-workflow.md`](wiki/Decisions/ADR-0001-wiki-workflow.md)
for the rationale.
