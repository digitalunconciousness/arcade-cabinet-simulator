# Building Arcade Fault Simulator

This guide is for contributors who want to build the app from source or work on the codebase.

---

## Prerequisites

### All platforms

| Tool | Minimum version | Install |
|------|----------------|---------|
| Git | any recent | https://git-scm.com |
| Python | 3.10+ | https://python.org |
| Rust + Cargo | 1.70+ | `curl https://sh.rustup.rs -sSf \| sh` |
| Tauri CLI v2 | 2.x | `cargo install tauri-cli --version "^2"` |

### Linux only

```bash
sudo apt install \
    libwebkit2gtk-4.1-dev \
    libjavascriptcoregtk-4.1-dev \
    libgtk-3-dev \
    libayatana-appindicator3-dev \
    librsvg2-dev \
    patchelf \
    xvfb
```

### Windows only

- [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (MSVC, x64)
- [WebView2 SDK](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) (usually already present)
- [NSIS](https://nsis.sourceforge.io/) — only needed if building the installer locally

---

## Clone and set up

```bash
git clone https://github.com/<org>/arcade-sim.git
cd arcade-sim

# Create and activate the Python venv
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

---

## Dev mode (no build required)

Run the Flask server and open the UI in a browser — no Rust or PyInstaller needed:

```bash
source .venv/bin/activate
python -m tools.cabinet_bus --port 5050
# Open http://127.0.0.1:5050 in a browser
```

---

## Tauri dev mode (WebKitGTK window)

Runs the real Tauri WebView against the live Flask server. Requires the full Rust + system WebView prerequisites above.

Terminal 1:
```bash
source .venv/bin/activate
python -m tools.cabinet_bus --port 5050
```

Terminal 2:
```bash
source .venv/bin/activate
cargo tauri dev
```

The Tauri shell connects to `http://127.0.0.1:5050` as the dev URL (configured in `src-tauri/tauri.conf.json`).

---

## Building the release AppImage / installer

### Step 1 — Build the Python sidecar (PyInstaller)

```bash
cd /path/to/arcade-sim
source .venv/bin/activate
bash build/pyinstaller/build.sh
# Produces: dist/arcade-sim-server  (Linux ELF or Windows PE)
```

The script auto-installs PyInstaller into the venv if it isn't present. The spec is at `build/pyinstaller/server.spec`.

### Step 2 — Build the Tauri shell

**Linux:**
```bash
APPIMAGE_EXTRACT_AND_RUN=1 NO_STRIP=1 cargo tauri build
```

**Windows / macOS:**
```bash
cargo tauri build
```

Artifacts land in:
- **Linux:** `src-tauri/target/release/bundle/appimage/*.AppImage` and `bundle/deb/*.deb`
- **Windows:** `src-tauri/target/release/bundle/nsis/*-setup.exe`

> **Linux note:** `APPIMAGE_EXTRACT_AND_RUN=1` is required on systems without `libfuse2` (Arch, Ubuntu 22.04+, Fedora 37+). It tells the AppImage tools bundled with Tauri to extract and run themselves without FUSE. `NO_STRIP=1` prevents the old bundled `strip` binary from failing on modern glibc libraries that use `.relr.dyn` relocations.

> Note: `cargo tauri build` automatically runs `bash build/pyinstaller/build.sh` via the `beforeBuildCommand` hook in `tauri.conf.json`. Step 1 is only needed separately if you want the sidecar binary for testing without building the full app.

---

## Running the tests

### Python unit tests

```bash
source .venv/bin/activate
pytest tests/
```

### Sidecar smoke test

```bash
bash tools/cabinet_bus/smoke_sidecar.sh
```

Launches `python -m tools.cabinet_bus --tauri-sidecar`, parses the port from stdout, hits `/api/health`, asserts `{"status":"ok"}`, and kills the process.

### Netlist tests (requires MAME `nltool`)

```bash
# Build MAME first; nltool is produced alongside the mame binary
./vendor/mame/nltool -test tests/netlist/fault_buffer_test.cpp
```

---

## Project structure (build-relevant paths)

```
build/
  pyinstaller/
    server.spec          ← PyInstaller spec
    build.sh             ← build script (Linux/macOS); use build.bat on Windows
    work/                ← PyInstaller temp dir (gitignored)
dist/
  arcade-sim-server      ← produced sidecar binary (gitignored except dev stub)
src-tauri/
  Cargo.toml             ← Rust dependencies (tauri 2, tauri-plugin-shell, ...)
  tauri.conf.json        ← app config: window, bundle, sidecar, permissions
  src/
    main.rs              ← entry point
    lib.rs               ← boot sequence, sidecar management, MAME picker
  capabilities/
    default.json         ← Tauri 2 permission grants
  icons/                 ← app icons (32x32, 128x128, 128x128@2x)
tools/
  cabinet_bus/
    server.py            ← Flask server (sidecar entry point)
    __main__.py          ← makes `python -m tools.cabinet_bus` work
    config.py            ← ~/.arcade-sim/config.json helpers
ui/
  index.html             ← main SPA
  app.js                 ← front-end logic + WebGL CRT pipeline (_crtGl)
  shaders/
    crt_*.glsl           ← GLSL ES 1.00 fragment shaders (10 effects)
```

---

## CI / release pipeline

Releases are produced by `.github/workflows/release.yml` on tags matching `v[0-9]+.*`.

The workflow:
1. **Linux job** (Ubuntu 22.04): installs Rust + WebKitGTK + Python, runs `build/pyinstaller/build.sh`, then `cargo tauri build` → AppImage + `.deb`.
2. **Windows job** (Windows Server 2022): installs Rust + Python, same sequence → NSIS `.exe`.
3. **macOS job**: disabled (`if: false`) pending test hardware.

Artifacts are attached to the GitHub Release automatically by `tauri-action`.

### Release channels

This repo now has two release channels:

1. **Stable** (`.github/workflows/release.yml`):
  - Triggered by SemVer tags like `v1.2.3`.
  - Publishes a normal GitHub release (not pre-release).
  - Uses `src-tauri/tauri.conf.json`.

2. **Nightly** (`.github/workflows/nightly.yml`):
  - Triggered by schedule (daily) or manual dispatch.
  - Publishes to a fixed prerelease tag `nightly`.
  - Uses `src-tauri/tauri.nightly.conf.json` with a separate app identifier
    (`com.arcade-sim.desktop.nightly`) so nightly installs can coexist with stable.
  - Sets version dynamically as `0.1.0-nightly.<run_number>` per CI run.

Nightly and stable are intentionally separate so updater feeds and installs do not cross over.

The release workflows derive updater download URLs from the current server URL,
which keeps the same build/release flow usable on GitHub or Forgejo-compatible
hosts.

For release operations details, see `docs/RELEASE_CHANNELS.md`.

### CI secrets

| Secret | Purpose |
|--------|---------|
| `TAURI_PRIVATE_KEY` | Tauri updater signing key (v2 format) |
| `TAURI_KEY_PASSWORD` | Password for the above |

These are not required for unsigned builds. For Windows code signing, add `WINDOWS_CERTIFICATE` and `WINDOWS_CERTIFICATE_PASSWORD` (PKCS#12 base64).

---

## Common issues

**`cargo tauri dev` waits forever for frontend**
Flask is not running. Start `python -m tools.cabinet_bus --port 5050` in another terminal first.

**`dist/arcade-sim-server-x86_64-unknown-linux-gnu` not found**
Tauri appends the target triple to the sidecar filename at build time. The dev stub at that path is a shell script — PyInstaller `build.sh` will overwrite it with the real ELF. If the stub is missing, re-run `build/pyinstaller/build.sh` once from the repo root.

**`libwebkit2gtk-4.1-dev` not found on Ubuntu 20.04**
Ubuntu 20.04 ships WebKitGTK 4.0. Either upgrade to 22.04, or change the dependency to `libwebkit2gtk-4.0-dev` and add `"features": ["webkit2gtk-4-0"]` to the `tauri` crate in `Cargo.toml`.

**Shader compile errors in WebKitGTK**
The shaders use GLSL ES 1.00 (`varying`, `texture2D`, `gl_FragColor`). If a new shader uses `#version 300 es` syntax it will fail in WebKitGTK. Stick to ES 1.00 or add a transpilation step. Compile errors are logged to the browser console as `[CRT shader] compile failed: <name>`.

**`failed to run linuxdeploy` — patchelf missing (Arch Linux)**
linuxdeploy requires `patchelf` to rewrite ELF RPATH entries. Arch does not install it by default:
```bash
sudo pacman -S patchelf
```
On Ubuntu/Debian it is part of the `patchelf` package (already listed in the apt prerequisites above).

**`failed to run linuxdeploy` — `strip` crashes on `.relr.dyn` ELF sections (Arch Linux / glibc ≥ 2.31)**
linuxdeploy bundles an old 2019 `strip` binary that cannot parse compressed relocation sections used by modern glibc. Fix: set `NO_STRIP=1` in the environment before running `cargo tauri build`. This env var is already set in `beforeBuildCommand` in `tauri.conf.json`.

**`Failed to run plugin: gtk (exit code: 1)` — gdk-pixbuf loaders directory missing (Arch Linux)**
gdk-pixbuf ≥ 2.44 (with glycin) no longer ships `/usr/lib/gdk-pixbuf-2.0/2.10.0/` on Arch, but `pkg-config` still reports that path. The bundled `linuxdeploy-plugin-gtk.sh` at `~/.cache/tauri/` has been patched to guard the `copy_tree` call with a directory existence check. If the cache is cleared and the plugin is re-downloaded, re-apply the patch: change the `copy_tree "$gdk_pixbuf_binarydir"` line to check `[ -d "$gdk_pixbuf_binarydir" ]` first. See `patches/` for context.
