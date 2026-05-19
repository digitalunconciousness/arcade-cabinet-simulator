# Build notes

## System packages (Arch)

```bash
sudo pacman -Syu --needed \
  base-devel git python python-pip nodejs npm \
  sdl2_ttf sdl2_image rapidjson asio portaudio portmidi \
  qt6-base qt6-tools libxinerama libxi libpulse alsa-lib \
  flac libvpx libjpeg-turbo \
  glm pugixml lua \
  kicad kicad-library kicad-library-3d \
  xorg-server-xvfb \
  fuse2 \
  gtkwave fd ripgrep
```

`xorg-server-xvfb` is required for `run-demo.sh` to stream MAME video to the
browser. Without it MAME opens a real window on `$DISPLAY` and the video feed
is unavailable.

`fuse2` is required by the AppImage toolchain (`linuxdeploy`) when building
the release bundle with `bash build-release.sh`. Without it the build falls
back to extract-and-run mode (`APPIMAGE_EXTRACT_AND_RUN=1`), which works but
is slower and noisier.

## Python venv

```bash
cd /home/jackie/arcade-sim
python -m venv .venv
source .venv/bin/activate
pip install pyparsing lark jsonschema flask
```

## MAME — Centipede + nltool fast iteration

```bash
cd vendor/mame
make -j3 SOURCES=src/mame/atari/centiped.cpp TOOLS=1
./mame -version
./nltool --version
```

- `SOURCES=...centiped.cpp` keeps the build small (only the Centipede
  driver + deps).
- `TOOLS=1` is REQUIRED to compile the netlist library and `nltool` —
  without it, our `FAULT_BUFFER` device never gets compiled because
  Centipede itself doesn't use the netlist solver.
- Linking memory peaks around 4 GB. With the 7.5 GB box we keep `-j3`;
  bumping to `-j4` risks the OOM killer.

## MAME — full arcade subtarget

```bash
cd vendor/mame
make -j2 SUBTARGET=arcade
```

Multi-hour build; only needed if we want to test against drivers other
than Centipede.

## Running the full demo

```bash
source .venv/bin/activate
bash tools/run-demo.sh
```

`run-demo.sh` starts Xvfb, MAME (from `vendor/mame/`, headless), and the
Flask cabinet-bus server in one shot. It waits for the plugin socket before
printing the URL. Open `http://127.0.0.1:5050`. Ctrl-C stops everything.

**Note:** MAME must be launched from inside `vendor/mame/` (the script does
this automatically) so it can find the `plugins/cabinet_bus/` directory.
Running `./vendor/mame/mame` from the repo root fails with
`Could not load plugin: cabinet_bus`.

## Running the desktop app locally

```bash
bash build-release.sh
```

This builds the PyInstaller sidecar, produces the Tauri AppImage, deploys
both to `~/Applications/`, and updates the `.desktop` entry.

The top-level `make` target runs the same rebuild-and-deploy flow:

```bash
make
```

Use `make package` or `bash build-release.sh --no-deploy` when you want
fresh artifacts without updating the installed desktop app.

For a quick iteration build without AppImage packaging:
```bash
cd /home/jackie/arcade-sim/src-tauri
cargo build --release
cd ..
bash tools/deploy-desktop.sh --launch
```

This deploys three things:

- `~/Applications/ArcadeFaultSimulator.AppImage` — current desktop binary
- `~/Applications/arcade-sim-server` — sidecar binary
- `~/.local/share/applications/arcade-fault-simulator.desktop` — App Center entry

Notes:

- The desktop app is now the canonical runtime for interactive gameplay.
- The deploy script writes `Path=/home/jackie/arcade-sim` into the desktop
  entry so App Center launches resolve bundled paths correctly.
- Boot diagnostics go to `/tmp/arcade-sim-boot.log`.
- The desktop shell starts `Xvfb :99` automatically and runs MAME headless.
- Real-time MAME input now goes through Tauri IPC and a Rust socket bridge;
  the browser-only `run-demo.sh` path remains useful for API and rendering
  work but is no longer the reference path for gameplay latency.

## Running MAME with audio

```bash
cd vendor/mame
./mame -rompath ../../roms -window -sound pipewire centiped3
```

The new audio system (~MAME 0.270+) replaced auto-routing with explicit
backend selection. Available drivers on this box: `pipewire`,
`pulseaudio`. To make the choice permanent:

```bash
./mame -createconfig
# edit mame.ini and set:  sound  pipewire
```

## Running nltool against our test netlists

```bash
./vendor/mame/nltool --cmd=run --time_to_run=0.005 -l FB1.Y \
    -D FAULT_MODE=1 tests/netlist/fault_buffer_test.cpp
head log_FB1.Y.log
```

## Incident notes: white screen + offline panel (May 2026)

### Root causes

- Linux WebKit subprocess instability under sandboxed launches from desktop/App Center.
- Socket bridge churn between Python client and Lua plugin caused status flapping/timeouts.
- Frontend runtime exceptions in `ui/app.js` (missing globals/constants after refactors) prevented status/UI updates, which looked like backend offline.
- Noisy reconnect and polling logs made it hard to distinguish true failures from healthy traffic.

### Fixes by file

- `src-tauri/src/main.rs`
  - Added Linux runtime hardening env setup (including sandbox-disable flag for this deployment mode).
- `tools/deploy-desktop.sh`
  - Updated desktop launcher env handling so App Center launches use the same runtime flags.
- `src-tauri/src/lib.rs`
  - Added boot log rotation and MAME process stdout/stderr capture to `/tmp/arcade-sim-mame.log`.
- `tools/cabinet_bus/server.py`
  - Enabled threaded Flask serving and added `/api/mame/diagnostic` endpoint.
- `tools/cabinet_bus/mame_client.py`
  - Reworked lock-safe socket lifecycle and retry behavior to avoid deadlock/reconnect loops.
- `vendor/mame/plugins/cabinet_bus/init.lua`
  - Improved listener startup retries and removed reconnect-on-idle behavior.
- `ui/app.js`
  - Restored required globals/constants and added null/guard checks in startup + peripheral/audio paths.

### Verification commands (desktop path)

Run from repo root unless noted:

```bash
# 1) Build and deploy desktop bits
bash build-release.sh

# 2) Confirm package outputs are fresh
find src-tauri/target -type f \( -name '*.AppImage' -o -name '*.deb' -o -name '*.rpm' \) \
  -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' | sort -r | head -n 10

# 3) Confirm deployed runtime artifacts
ls -l ~/Applications/ArcadeFaultSimulator.AppImage ~/Applications/arcade-sim-server

# 4) Confirm desktop entry used by launcher
sed -n '1,200p' ~/.local/share/applications/arcade-fault-simulator.desktop

# 5) Inspect startup diagnostics
tail -n 60 /tmp/arcade-sim-boot.log
tail -n 60 /tmp/arcade-sim-mame.log
```

### Healthy signals

- UI status text transitions to `ready`.
- MAME panel is visible and offline placeholder is hidden.
- `/api/mame/state` and `/api/peripherals/state` return HTTP 200 repeatedly.
- `/tmp/arcade-sim-boot.log` shows Xvfb + MAME + sidecar startup without crash loops.
- `/tmp/arcade-sim-mame.log` shows MAME/plugin activity instead of immediate process exit.

### If X then check Y

- If App Center launch shows white screen, check launcher entry and Linux WebKit env in `tools/deploy-desktop.sh` and `src-tauri/src/main.rs`.
- If panel stays offline but APIs are 200, check browser console/runtime errors and recent edits in `ui/app.js`.
- If `/api/mame/*` hangs or times out, check socket bridge logs/diagnostic endpoint and `tools/cabinet_bus/mame_client.py` lock behavior.
- If plugin repeatedly disconnects/reconnects, check `vendor/mame/plugins/cabinet_bus/init.lua` reconnect policy.
- If boot log looks healthy but no cabinet state changes, confirm MAME was launched from `vendor/mame/` so plugin discovery works.

### Morning checklist

```bash
cd /home/jackie/arcade-sim
source .venv/bin/activate
bash build-release.sh

# quick health check
python - <<'PY'
import requests
for url in [
    'http://127.0.0.1:5050/api/mame/state',
    'http://127.0.0.1:5050/api/peripherals/state',
]:
    try:
        r = requests.get(url, timeout=2)
        print(url, r.status_code)
    except Exception as e:
        print(url, 'ERR', e)
PY

tail -n 30 /tmp/arcade-sim-boot.log
```

## Common errors

| Error | Cause |
| ----- | ----- |
| `Required files are missing, the machine cannot be run.` | ROM set name mismatch (try `centiped3` for the rev-3 ROMs). |
| `Input FB.GND already connected` | Don't list `FB.GND` in `NET_C(GND, ...)`; `@GND` auto-connects. |
| `tristate output FB.Y on device FB is connected to an analog net` | Set `PARAM(FB.FORCE_TRISTATE_LOGIC, 0)` for analog tristate. |
| `Unknown parameter FB.0` | Macro substitution collision — rename the `-D` macro (avoid `MODE`). |
| `make: Nothing to be done for ...` | Wrong target; with this tree just run `make -j3 SOURCES=... TOOLS=1`. |
| `fatal: No names found, cannot describe anything.` during build | Benign — shallow git clone has no tags. MAME embeds "unknown" in version. |
| `Could not load plugin: cabinet_bus` | MAME launched from wrong directory — must run from inside `vendor/mame/`. |
| `port 5050/5051 already in use` | Kill stale processes: `pkill -f 'mame\|cabinet_bus'`, then retry. |
| `failed to bundle project 'failed to run linuxdeploy'` / `unknown type [0x13] section '.relr.dyn'` | Old `strip` inside linuxdeploy fails on modern glibc. Use `bash build-release.sh` (sets `NO_STRIP=1`) or pass `NO_STRIP=1` manually. |

## Disk usage at end of Phase 1

- `vendor/mame/` (source + build): about 7 GB
- `vendor/discrete/`: ~1 MB
- `.venv/`: ~20 MB
- workspace tracked content: <1 MB
