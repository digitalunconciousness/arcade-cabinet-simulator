# Desktop App — Fully Integrated Demo

The desktop app (Tauri) now fully integrates MAME, Xvfb, and the Flask server. When you launch the app, everything starts automatically—no manual setup required.

## Prerequisites

**System packages required:**
```bash
# Arch Linux:
sudo pacman -S xorg-server-xvfb ffmpeg xdotool

# Ubuntu/Debian:
sudo apt-get install xvfb ffmpeg xdotool

# macOS (if running on Mac):
brew install xquartz ffmpeg
```

**MAME binary:**
- Built and available in `vendor/mame/mame`, OR
- Installed in PATH (e.g., `/usr/bin/mame`), OR
- Path saved in `~/.arcade-sim/config.json`

**ROM files:**
- `roms/centiped3.zip` (required for Centipede demo)

**Config files:**
- `cfg/` directory with `centiped3.cfg` and `default.cfg`

## Running the Desktop App

### Option 1: Development Mode
```bash
cd /home/jackie/arcade-sim/src-tauri
cargo tauri dev
```

This will:
1. Build the Rust frontend + Tauri shell
2. Start the Flask sidecar (arcade-sim-server)
3. Automatically launch Xvfb on :99
4. Automatically launch MAME with cabinet_bus plugin
5. Open the web UI in the Tauri window with live MAME video

### Option 2: Release Build (AppImage)
```bash
cd /home/jackie/arcade-sim/src-tauri
NO_STRIP=1 APPIMAGE_EXTRACT_AND_RUN=1 cargo tauri build
```

This creates a bundled AppImage at `src-tauri/target/release/bundle/appimage/arcade-sim_*.AppImage` that includes:
- All dependencies (Python sidecar, MAME binary, ROMs, configs)
- Xvfb support
- FFmpeg streaming

Then run:
```bash
./arcade-sim_*.AppImage
```

## Boot Sequence

When you launch the app:

```
[arcade-sim] starting Xvfb on :99…          (virtual X11 display)
  ↓
[arcade-sim] starting MAME…                 (emulator + cabinet_bus plugin)
  ↓
[arcade-sim] starting arcade-sim-server sidecar…  (Flask HTTP API)
  ↓
[arcade-sim] sidecar listening on PORT=5050
  ↓
Window navigates to http://127.0.0.1:5050
  ↓
LIVE: MAME output visible in window, all controls responsive
```

Full startup takes ~5–10 seconds.

## What's Fully Integrated

✓ Xvfb virtual display management  
✓ MAME emulator launch  
✓ Cabinet bus plugin communication  
✓ Flask API server  
✓ Live MAME video stream (MJPEG)  
✓ Fault injection (peripherals, RAM, CRT)  
✓ All UI controls  
✓ Scenario demos  
✓ Graceful multi-process cleanup on exit  

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Xvfb spawn failed" | Install xorg-server-xvfb: `sudo pacman -S xorg-server-xvfb` |
| "MAME spawn failed" / not found | Ensure MAME is built or in PATH; check `~/.arcade-sim/config.json` |
| "ROM path not found" | Verify `roms/centiped3.zip` exists |
| "Socket already in use" | Previous app instance didn't exit cleanly; wait 10s or reboot |
| Black window on launch | Give it 8–10 seconds; MAME and Xvfb are initializing |
| Video stream not showing | Check `ffmpeg` is installed; verify DISPLAY env is set |

## Environment Configuration

The app automatically sets:
- `DISPLAY=:99` for Xvfb
- `MAME_DISPLAY=:99` for video capture
- `SDL_VIDEODRIVER=x11` for X11 graphics
- `PYTHONHOME=""` and `PYTHONPATH=""` for PyInstaller sidecar

To override MAME binary location, edit `~/.arcade-sim/config.json`:
```json
{
  "mame_binary": "/path/to/mame",
  "rom_path": "/path/to/roms",
  "display": ":99"
}
```

## Architecture

```
┌─────────────────────────────┐
│  Tauri Window (WebView)     │
│  (localhost:5050)           │
└──────────────┬──────────────┘
               │
       ┌───────┴────────┬──────────────┬─────────────────┐
       │                │              │                 │
   ┌───▼──┐      ┌──────▼────┐  ┌─────▼────┐     ┌──────▼──────┐
   │ Xvfb │      │   MAME    │  │  Flask   │     │   Cabinet   │
   │ :99  │      │Centipede  │  │  Server  │     │    Bus      │
   │      │      │ +Plugin   │  │  (sidecar)      │  (TCP:5051) │
   └──────┘      └────┬──────┘  └──────────┘     └─────────────┘
                      │
              MJPEG stream to UI
              (ffmpeg capture)
```

## Next: Full Development Setup

The desktop app is now the primary interface. All UI work, API development, and fault scenario creation happen here. The web demo (`tools/run-demo.sh`) remains available for direct debugging without the Tauri wrapper.

---

**Ready to launch?** Just run `cargo tauri dev` and watch the magic happen! 🎮

