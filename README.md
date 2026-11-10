# Arcade Cabinet Fault Simulator

Runs a real arcade ROM in MAME (Centipede first) and lets you inject hardware faults and watch the game break.
The goal is a native Windows and Linux app with a 3D cabinet, simulated troubleshooting and repair, and a
"cabinet pack" format so other people can add games.

- **Plan:** [`docs/PLAN_v3.md`](docs/PLAN_v3.md) is the source of truth. Where it conflicts with
  `arcade_cabinet_fault_simulator_plan.md` (v0.2) or the wiki, PLAN_v3 wins.
- **What works today:** [`docs/STATUS.md`](docs/STATUS.md) lists what is real, mocked and unproven.
- **Which faults reach the game:** [`docs/FAULT_AUDIT.md`](docs/FAULT_AUDIT.md), with evidence in `evidence/stage0/`.
- **Rules for contributors and agents:** [`CLAUDE.md`](CLAUDE.md). Parked ideas: [`docs/BACKLOG.md`](docs/BACKLOG.md).

The desktop app on `main` is still the legacy Tauri + Xvfb + MJPEG + Flask shell (Linux only). It stays until the
Godot spike in Stage 2 works ([ADR-0011](wiki/Decisions/ADR-0011-Native-Shell-Direction.md)).

## Layout (tracked)
- `patches/` — patch series we keep on top of MAME, applied to the tag in `patches/MAME_VERSION`. See
  `patches/README.md`.
- `plugin/cabsim/` — the fault engine, a MAME Lua plugin (primitives, headless timeline mode, Sim Control Protocol v1).
- `tools/cabsim/` — the effect-test runner (`python -m tools.cabsim effect run ...`), benchmark and protocol smoke test.
- `tests/effect/` — one effect test per fault, for the real game (`centipede/`) and the original test ROM (`testrom/`).
- `testrom/` — the original 6502 test program and assembler that CI runs the fault primitives on.
- `tools/ci/build-mame.sh` — builds the pinned, patched MAME into `mame-bin/` (CI and local).
- `.forgejo/workflows/`, `tools/forgejo/` — CI on a self-hosted Forgejo; setup in [`docs/ci-forgejo.md`](docs/ci-forgejo.md).
- `evidence/` — committed test output and images (`stage0/` legacy audit, `stage1/` fault engine).
- `tools/audit/` — the Stage 0 truth audit (headless runs of every legacy fault).
- `tools/preprocessor/` — Python auto-instrumentation tool that walks a
  netlist `.cpp` and inserts `FAULT_BUFFER` on every fault-eligible pin,
  emitting a JSON manifest.
- `tests/netlist/` — nltool harness netlists for the fault-injection devices. They run standalone and are not
  connected to the running game.
- `docs/devices/` — documentation for the netlist devices we add to MAME.
- `ui/`, `src-tauri/`, `tools/cabinet_bus/` — the legacy web UI, Tauri shell and Flask server.
## Layout (untracked, gitignored)
- `vendor/mame/` — MAME cloned at the pinned tag, with `patches/*.patch` applied.
- `vendor/discrete/` — MAME-KiCad bridge (`mamedev/discrete`).
- `roms/` — your own ROM set. Never committed, pushed or bundled ([ADR-0012](wiki/Decisions/ADR-0012-ROM-Policy.md)).
- `docs/{centipede,wells-gardner,cojag}/` — service manuals (PDFs).
- `scans/centipede/` — Sean Riddle PCB scans + our freshly-refit board scans.
- `scratch/` — throwaway experiments.
- `.venv/` — Python venv.
## Bootstrapping a fresh checkout
```bash
# 1. Clone the workspace.
git clone <this repo> arcade-sim && cd arcade-sim
# 2. Pull the pinned MAME tag and apply our patch series.
read -r MAME_TAG MAME_SHA < patches/MAME_VERSION
git clone --depth=1 --branch "$MAME_TAG" https://github.com/mamedev/mame.git vendor/mame
git -C vendor/mame am "$PWD"/patches/*.patch
git clone --depth=1 https://github.com/mamedev/discrete.git vendor/discrete
# 3. Python venv.
python -m venv .venv
source .venv/bin/activate
pip install pyparsing lark jsonschema flask
# 4. Legacy desktop app only: install Xvfb (headless X11 for the video stream).
#    Arch: sudo pacman -S xorg-server-xvfb
#    Debian/Ubuntu: sudo apt install xvfb
# 5. Build MAME (Centipede driver + nltool).
cd vendor/mame
make -j"$(nproc)" SOURCES=src/mame/atari/centiped.cpp TOOLS=1 USE_QTDEBUG=0
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
## Legacy demo (Phase 7 vertical slice)

This section describes the legacy app as it was documented. The Stage 0 audit found that most of its faults don't
change the running game in a build made from this repo; see [`docs/FAULT_AUDIT.md`](docs/FAULT_AUDIT.md).

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
