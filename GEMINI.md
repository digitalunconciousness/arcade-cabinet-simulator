# Arcade Cabinet Fault Simulator - Project Context

## Project Overview
The **Arcade Cabinet Fault Simulator** is a high-fidelity simulation environment for arcade hardware, focusing on the **Atari Centipede** cabinet. It combines gate-level netlist simulation for PCBs with behavioral modeling for peripherals (PSU, CRT, controls) to provide a platform for diagnostic research and technician training.

### Core Architecture
- **Simulator Core:** A patched version of **MAME** (tracked in `vendor/mame/`) using its netlist solver for PCB logic.
- **Fault Injection:** Custom `FAULT_BUFFER` and `BAD_RAM_CELL` devices in MAME, inserted via an auto-instrumentation preprocessor.
- **Cabinet Bus:** A JSON/TCP bridge (Lua-based inside MAME) that synchronizes the PCB with external peripheral models.
- **Peripheral Models:** Python-based behavioral models for the Power Supply Unit (PSU), CRT (using GLSL shaders for faults), trackball, and coin mechanism.
- **User Interface:** A Flask-based web UI for visualization, fault injection, and training scenarios. A **Tauri** shell (`src-tauri/`) provides the desktop application wrapper.
- **Training Mode:** A scenario-based system that injects realism-weighted faults for users to diagnose.

## Tech Stack
- **Languages:** C++ (MAME), Python (Preprocessor, Server, Models), JavaScript/HTML/CSS (UI), Rust (Tauri), Lua (MAME plugins).
- **Key Libraries:** 
  - **Python:** `flask`, `pyparsing`, `lark`, `jsonschema`, `pytest`.
  - **MAME:** Netlist library, BGFX (shaders).
  - **Other:** `ffmpeg` (video streaming), `Xvfb` (headless display).

## Building and Running

### 1. Bootstrapping
Requires Python 3.10+, MAME build dependencies, and `Xvfb`.
```bash
# Setup venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Setup MAME (if not already done)
git clone --depth=1 https://github.com/mamedev/mame.git vendor/mame
( cd vendor/mame && git am ../../patches/*.patch )
```

### 2. Building MAME
Focuses on the Centipede driver and netlist tools:
```bash
cd vendor/mame
make -j"$(nproc)" SOURCES=src/mame/atari/centiped.cpp TOOLS=1
```

### 3. Running the Demo
Starts MAME (headless), the Cabinet Bus server, and the UI:
```bash
bash tools/run-demo.sh
```
Access the UI at `http://127.0.0.1:5050`.

### 4. Instrumentation
Use the preprocessor to add fault points to a netlist `.cpp`:
```bash
python -m tools.preprocessor.instrument \
    --input  src/mame/atari/centiped_nl.cpp \
    --output build/instrumented/centiped_nl.cpp \
    --manifest build/instrumented/centiped_nl.manifest.json
```

## Development Conventions

### Documentation & Wiki
- The project uses an **in-repo wiki** located in `wiki/`.
- Phase-based progress is tracked in `wiki/Phases/`.
- To sync the local wiki to GitHub: `bash tools/sync-wiki.sh`.

### MAME Patches
- Do not modify `vendor/mame/` directly. 
- Maintain changes as patches in `patches/`.
- Use `git am` to apply and `git format-patch` to update the patch series.

### Fault Injection
- Prefer auto-instrumentation via `tools/preprocessor/` over manual netlist edits for fault points.
- New fault devices (C++) should be documented in `docs/devices/` and added to `patches/`.

### Testing
- **Python Tools:** Run `pytest` in the root or specific tool directories.
- **Netlist Logic:** Use `nltool` with test files in `tests/netlist/`.
- **Smoke Tests:** `tests/smoke/test_bundle.py` verifies the end-to-end integration.

## Key Directory Structure
- `boards/`: Board-specific metadata and KiCad netlist exports.
- `build/`: Target for instrumented code and generated manifests.
- `patches/`: The core patch series for MAME.
- `src-tauri/`: Desktop application wrapper logic.
- `tools/`:
  - `cabinet_bus/`: Server and bridge implementation.
  - `preprocessor/`: Instrumentation logic.
  - `peripherals/`: Behavioral models for PSU, CRT, etc.
- `ui/`: Frontend assets (HTML, JS, CSS, Shaders).
- `wiki/`: Architectural Decision Records (ADRs) and project roadmap.
