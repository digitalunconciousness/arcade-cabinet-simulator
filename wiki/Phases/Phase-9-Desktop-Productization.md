# Phase 9 — Desktop productization

**Status:** ✅ complete (Linux-first desktop shell shipped; current runtime is desktop-first)
**Goal:** Convert the current local web/server prototype into a downloadable desktop application for Linux first, then Windows, then macOS when hardware is available for validation.
**Estimate:** 6-10 weekends after Phase 8.

## Why this phase matters

- The current server model is correct for development, but it is not the final user experience.
- A downloadable app forces a clean runtime contract: bundled assets, predictable paths, self-checks for MAME availability, and reproducible install behavior.
- Cross-platform packaging is easier before the 3D cabinet work increases the asset surface.

## Product target

One local desktop application per supported platform that launches a local
desktop shell and runs without the user manually starting Flask, opening a
browser, or setting environment variables.

## Technology decision — Tauri

### Chosen stack

Tauri (Rust shell + system WebView + Python sidecar)

After evaluating three candidates:

| Path | Bundle size | UI rewrite? | Reason not chosen |
| ---- | ----------- | ----------- | ----------------- |
| Tauri | 5–15 MB | none | chosen |
| Electron | 150–500 MB | none | too large; ships full Chromium |
| PySide/PyQt | 40–80 MB | full rewrite | loses WebGL shader system |

Rationale:

1. **Zero UI rewrite.** The existing HTML/CSS/JS/WebGL UI stays in place. Tauri wraps it in the system WebView and now also exposes a direct IPC path for latency-sensitive controls.
2. **Python sidecar pattern.** The Flask server is compiled to a standalone sidecar binary via PyInstaller and launched as a managed child process. The desktop shell reads the sidecar port from stdout, waits for `/api/health`, then opens the live UI.
3. **Small desktop shell.** The Tauri shell stays lightweight and lets the larger assets remain in the Python sidecar / resource bundle.
4. **Platform control.** Rust owns process orchestration, stale-process cleanup, splash-state reporting, App Center launch behavior, and direct plugin-socket control for gameplay input.

Risks:

- Rust toolchain is a new build dependency (mitigated: only needed for the shell; daily development still runs server directly).
- WebKitGTK rendering differs slightly from Chrome. The existing shaders must be validated on the target WebView version.
- macOS code signing requires an Apple Developer account and test hardware; deferred until available.

ADR filed at: `wiki/Decisions/ADR-0009-Desktop-Shell-Tauri.md`

## What actually shipped

- `src-tauri/src/lib.rs` manages the full boot sequence: stale-process cleanup,
  `Xvfb :99`, MAME with `-plugin cabinet_bus`, sidecar launch, `/api/health`
  probe, and WebView navigation.
- `ui/splash.html` is the boot surface and shows progress/error state while
  MAME and the sidecar come up.
- `tools/deploy-desktop.sh` is the current operator-facing deploy path. It
  copies both the desktop binary and the sidecar into `~/Applications/`, then
  writes `~/.local/share/applications/arcade-fault-simulator.desktop` with a
  fixed `Path=` entry so App Center launches are reliable.
- Boot logging now goes to `/tmp/arcade-sim-boot.log`, which records path
  resolution and early failures for non-terminal launches.
- Real-time control input no longer goes through Flask + `xdotool` in the
  shipped desktop build. `ui/app.js` calls `window.__TAURI__.core.invoke(...)`,
  Rust keeps a persistent socket connection to the MAME plugin, and commands
  are forwarded directly to `127.0.0.1:5051`.
- `src-tauri/tauri.conf.json` sets `withGlobalTauri: true` so the vanilla JS
  frontend can use Tauri IPC without a bundler-specific import step.

## Implementation milestones

### ✅ Milestone 1 — Python sidecar contract (1–2 weekends)

- `--tauri-sidecar` flag in `tools/cabinet_bus/server.py` ✅
- `/api/health` endpoint returning `{"status": "ok", "board_id": <str|null>}` ✅
- `tools/cabinet_bus/__main__.py` — `python -m tools.cabinet_bus` works ✅
- `tools/cabinet_bus/smoke_sidecar.sh` smoke test ✅

### ✅ Milestone 2 — PyInstaller bundle (1–2 weekends)

- `build/pyinstaller/server.spec` — bundles cabinet_bus, schematic, peripherals, training, boards/, ui/, scenarios/ ✅
- `build/pyinstaller/build.sh` — activates venv, auto-installs PyInstaller if missing, produces `dist/arcade-sim-server` ✅
- `_bundle_root()` helper in `server.py` — resolves data paths from `sys._MEIPASS` when frozen ✅

### ✅ Milestone 3 — Tauri app scaffold + MAME/Xvfb platform config (1–2 weekends)

- `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml`, `src-tauri/src/lib.rs`, `src-tauri/src/main.rs` ✅
- Boot sequence: spawn sidecar → parse `PORT=<n>` from stdout → health-check poll → navigate WebView ✅
- Splash screen (`ui/splash.html`) shown during boot ✅
- Boot progress and boot error reporting on the splash screen ✅
- App Center launch support via `.desktop` entry `Path=` and explicit project-root discovery ✅
- `/tmp/arcade-sim-boot.log` diagnostics for non-terminal launches ✅
- `tools/cabinet_bus/config.py` — `~/.arcade-sim/config.json` with `mame_binary`, `rom_path`, `display` ✅
- Env var overrides: `ARCADE_SIM_MAME_BINARY`, `ARCADE_SIM_ROM_PATH`, `ARCADE_SIM_DISPLAY` ✅
- `/api/mame/runtime_info` endpoint ✅
- First-run MAME picker dialog (Tauri native file dialog) ✅
- `cargo check` passes cleanly on Tauri 2.11.0 ✅

### ✅ Milestone 4 — First-run ROM path setup (0.5–1 weekend)

- Covered in M3 above: native file picker on first run, `ARCADE_SIM_ROM_PATH` env var, guided error when MAME absent ✅

### ✅ Milestone 5 — WebKitGTK shader validation (1 weekend)

- All 10 `ui/shaders/crt_*.glsl` shaders confirmed compatible with WebGL 1 / GLSL ES 1.00 (no `#version 300 es`) ✅
- `_crtGl` WebGL pipeline added to `ui/app.js`: fetches shaders at init, runs GPU path, falls back to Canvas 2D ✅
- `[gl]` suffix in CRT preview meta confirms WebGL active at runtime ✅

### ✅ Milestone 6 — Deploy/release pipeline (1–2 weekends)

- `.github/workflows/release.yml` written — Linux (Ubuntu 22.04 → AppImage + .deb) and Windows (Windows Server 2022 → NSIS) jobs using `tauri-action` pattern ✅
- `tests/smoke/test_bundle.py` written — launches sidecar, checks `/api/health`, `/api/scenarios`, applies `01-dim-psu-5v`, checks `/api/mame/runtime_info`, verifies static assets ✅
- `NO_STRIP=1 APPIMAGE_EXTRACT_AND_RUN=1` baked into `beforeBuildCommand` (workaround for Arch Linux / glibc ≥ 2.31 `.relr.dyn` sections) ✅
- `tools/deploy-desktop.sh` written — local Linux deploy loop for `~/Applications/` and App Center ✅
- Trigger: tags matching `v[0-9]+.*`
- GitHub repository + push access required to activate workflow

### ✅ Milestone 6.5 — Low-latency desktop input path

- `src-tauri/tauri.conf.json` enables `withGlobalTauri` ✅
- `ui/app.js` uses `window.__TAURI__.core.invoke(...)` for MAME input ✅
- `src-tauri/src/lib.rs` provides `mame_press_button`, `mame_release_button`, and `mame_trackball_delta` commands ✅
- Rust keeps a persistent socket bridge to the MAME plugin and retries once on disconnect ✅

### ✅ Milestone 7 — Documentation + release notes (0.5 weekend)

- `docs/INSTALL.md` written — Linux AppImage/deb, Windows NSIS, MAME setup, config file, env var table ✅
- `docs/BUILD.md` written — full contributor guide with prerequisites, build steps, CI pipeline, and Arch Linux workarounds ✅
- Wiki updated to ✅ complete ✅
- Local desktop deploy path documented and repeatable ✅

## File layout inside the release bundle

```text
arcade-sim/                  <- AppImage, deb, or local desktop deploy root
  arcade-sim-server          <- PyInstaller sidecar binary
  boards/                    <- bundled board packages
    centipede/
      board.json
      schematic.board.json
      fault_map.json
  tests/scenarios/           <- bundled training scenarios
  ui/                        <- static assets served by Flask
  vendor/mame/mame[.exe]     <- bundled MAME binary in the current Linux-first flow
  README.txt                 <- minimal launch instructions
```

## Definition of done

1. Linux desktop app can be built and deployed locally without manually starting Flask or opening a browser.
2. App boot flow reports progress and shows a useful error if MAME or the sidecar fails.
3. App Center launches are stable and resolve project/resource paths correctly.
4. Board packages, scenarios, shaders, and bundled resources are available to the desktop runtime.
5. The user can apply faults and control the running game without touching a terminal.
6. Real-time gameplay input avoids the old HTTP + `xdotool` path in the shipped desktop runtime.
7. `docs/INSTALL.md`, `docs/BUILD.md`, and the canonical wiki pages are accurate.

## Post-ship improvements

The following features were added after the Phase 9 baseline was committed.
They are bundled in the same AppImage and do not constitute a new phase.

### Live fault diagnostics in the MAME stats panel

- **Stuck bytes counter** — `snapshot_state()` in the Lua plugin now returns
  `stuck_count` (number of RAM addresses currently stuck). The value is
  displayed in the MAME stats grid and turns amber when non-zero.
- **CRT overlay indicator** — `snapshot_state()` also returns `crt_effect`
  (e.g. `"burn-in"`, `"normal"`) and `crt_brightness`. The indicator turns
  amber when any non-normal CRT fault is active.

These give the technician trainee immediate visual confirmation that a fault
scenario has taken effect in the emulator — previously there was no in-UI
feedback beyond the game's video output.

### DIP Switches panel

A *DIP Switches…* button in the MAME controls area opens a modal dialog that
enumerates all named DIP switch fields from the running game's `ioport`
system. Each switch appears as a labelled `<select>` dropdown. Changing a
value sends a `POST /api/mame/dip_switch` request which calls
`manager.machine.ioport.ports[tag].fields[name]:set_value(v)` in the Lua
plugin.

- `GET /api/mame/dip_switches` — list all ports + fields + current values
- `POST /api/mame/dip_switch` — set `{port, name, value}`
- Lua: `list_dip_switches` / `set_dip_switch` command handlers
- Python: `MameClient.list_dip_switches()` / `MameClient.set_dip_switch()`

This allows instructors to pre-configure the game (lives, bonus life,
difficulty) without leaving the simulator UI.

### Build process — proper AppImage packaging

The project now ships a proper AppImage (produced by `linuxdeploy` via
`cargo tauri build`) rather than a raw ELF copy. A `build-release.sh`
wrapper at the repo root encodes the required `NO_STRIP=1` and
`APPIMAGE_EXTRACT_AND_RUN=1` env vars so the build just works. `fuse2` added
to system prerequisites.

### Fault injection reliability fixes

- `fetchJSON` helper re-added to `app.js` (had been deleted in a previous
  commit while call sites remained, causing silent failures).
- `postJSON` now throws on non-2xx responses instead of returning `null`.
- Apply/Clear scenario buttons are mutually disabled while a request is
  in-flight (prevents double-submissions and stuck button states).
- `api_scenario_clear` now flushes stuck bytes and CRT state in MAME before
  running the scenario's clear-faults list.
- `schematic_faults` dict now protected by a `threading.Lock` to prevent
  data races when multiple endpoints read/write it concurrently.

## Navigation

← Previous: [Phase 8 — Schematic board packages + training surfaces](Phase-8-Schematic-Board-Package.md) ·
Next: [Phase 10 — 3D cabinet digital twin](Phase-10-3D-Cabinet-Digital-Twin.md) →
