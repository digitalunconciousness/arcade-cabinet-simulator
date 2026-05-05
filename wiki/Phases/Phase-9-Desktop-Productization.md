# Phase 9 — Desktop productization
**Status:** 🚧 in progress (M1–M5 complete; M6 CI pipeline + M7 docs remain)
**Goal:** Convert the current local web/server prototype into a downloadable desktop application for Linux first, then Windows, then macOS when hardware is available for validation.
**Estimate:** 6-10 weekends after Phase 8.

## Why this phase matters
- The current server model is correct for development, but it is not the final user experience.
- A downloadable app forces a clean runtime contract: bundled assets, predictable paths, self-checks for MAME availability, and reproducible install behavior.
- Cross-platform packaging is easier before the 3D cabinet work increases the asset surface.

## Product target
One installer per supported platform that launches a local desktop shell and runs without the user manually starting Flask, opening a browser, or setting environment variables.

## Technology decision — Tauri
**Chosen: Tauri (Rust shell + system WebView + Python sidecar)**

After evaluating three candidates:

| Path | Bundle size | UI rewrite? | Reason not chosen |
|------|------------|-------------|-------------------|
| Tauri | 5–15 MB | none | **chosen** |
| Electron | 150–500 MB | none | too large; ships full Chromium |
| PySide/PyQt | 40–80 MB | full rewrite | loses WebGL shader system |

Rationale:
1. **Zero UI changes.** The existing HTML/CSS/JS/WebGL UI is already production-quality. Tauri wraps it in a system WebView (WebKitGTK on Linux, WebView2 on Windows) with no modifications.
2. **Python sidecar pattern.** Tauri has first-class support for sidecar binaries. The Flask server is compiled to a standalone executable via PyInstaller and launched as a managed child process. The Tauri shell reads the port number from the sidecar's stdout, then opens the WebView to `http://127.0.0.1:{port}`.
3. **Tiny bundles.** A Tauri AppImage for Linux typically reaches 10–20 MB including the Python sidecar. This matters because the ROM set itself is already large enough.
4. **Build CI.** `tauri-action` for GitHub Actions produces Linux AppImage + `.deb`, Windows NSIS installer, and macOS `.dmg` from a single workflow.

Risks:
- Rust toolchain is a new build dependency (mitigated: only needed for the shell; daily development still runs server directly).
- WebKitGTK rendering differs slightly from Chrome. The existing shaders must be validated on the target WebView version.
- macOS code signing requires an Apple Developer account and test hardware; deferred until available.

ADR filed at: `wiki/Decisions/ADR-Phase9-Desktop-Shell-Tauri.md`

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

### Milestone 6 — CI/release pipeline (1–2 weekends)
- Add `.github/workflows/release.yml` using `tauri-action`:
  - Linux: Ubuntu 22.04, produces AppImage + `.deb`.
  - Windows: Windows Server 2022, produces NSIS installer.
  - macOS: gated on `[macOS]` label in the PR title until hardware exists.
- Add `tests/smoke/test_bundle.py`: launch sidecar, GET `/api/health`, apply `01-dim-psu-5v.json`, assert 200.
- Trigger on tags matching `v[0-9]+.*`.

### Milestone 7 — Documentation + release notes (0.5 weekend)
- `docs/INSTALL.md` for each platform.
- `docs/BUILD.md` for contributors (Rust + Python prerequisites, CI secrets).
- Update `wiki/Phases/Phase-9-Desktop-Productization.md` to ✅ complete.

## File layout inside the release bundle
```
arcade-sim/                  ← AppImage or NSIS root
  arcade-sim-server           ← PyInstaller sidecar binary
  boards/                     ← bundled board packages
    centipede/
      board.json
      schematic.board.json
      fault_map.json
  tests/scenarios/            ← bundled training scenarios
  ui/                         ← static assets served by Flask
  vendor/mame/mame[.exe]      ← MAME binary (user must supply or configure)
  README.txt                  ← minimal launch instructions
```

## Definition of done
1. Linux AppImage can be downloaded and run on a clean Ubuntu 22.04 machine without installing Python or Rust.
2. Windows NSIS installer can be run on a clean Windows 10/11 machine.
3. App boot flow checks for MAME and reports a clear guided error when absent.
4. Board packages, scenarios, shaders, and media assets are bundled in the release.
5. The user can apply and clear faults without touching a terminal.
6. CI produces signed release artifacts on every version-tagged commit.
7. `docs/INSTALL.md` and `docs/BUILD.md` exist and are accurate.

## Navigation
← Previous: [Phase 8 — Schematic board packages + training surfaces](Phase-8-Schematic-Board-Package.md) ·
Next: [Phase 10 — 3D cabinet digital twin](Phase-10-3D-Cabinet-Digital-Twin.md) →