# Installing Arcade Fault Simulator

## Requirements

- A legal **Centipede ROM set** (`centiped3` or compatible) in a directory you choose.
- The installer bundles a tested **MAME** runtime and required `cabinet_bus` plugin files.
  You can still override with your own MAME path in config if needed.
- For Linux: 64-bit x86 system running Ubuntu 20.04+ or equivalent (glibc 2.31+).
- For Windows: Windows 10 version 1803 or later (WebView2 must be installed — it ships with Windows 11 and is auto-installed on Windows 10 by Windows Update).

---

## Linux — AppImage

1. Download `arcade-fault-simulator_x.y.z_amd64.AppImage` from the Releases page.

2. Make it executable and run it:
   ```bash
   chmod +x arcade-fault-simulator_x.y.z_amd64.AppImage
   ./arcade-fault-simulator_x.y.z_amd64.AppImage
   ```

3. On **first launch**, the app validates the bundled MAME runtime.

4. A dialog asks for your ROM directory. Point it at the folder containing `centiped3.zip`.

5. If bundled MAME is missing or invalid on your machine, the app falls back
  to a file picker for a local MAME binary and stores the path in `~/.arcade-sim/config.json`.

6. The simulator window opens. Click **Load → Centipede Rev 3**, then select a fault scenario from the left panel.

### Linux — `.deb` package

```bash
sudo dpkg -i arcade-fault-simulator_x.y.z_amd64.deb
arcade-fault-simulator
```

The `.deb` installs to `/opt/arcade-fault-simulator/`.

### MAME under Xvfb (headless)

The simulator hides the MAME SDL window by running it on a virtual framebuffer (`Xvfb :99`). You do **not** need a display manager or X session — the AppImage starts Xvfb automatically. Video from MAME reaches the simulator UI via an MJPEG stream.

If you want to use a display other than `:99`, set the env var before launching:
```bash
ARCADE_SIM_DISPLAY=:2 ./arcade-fault-simulator_x.y.z_amd64.AppImage
```

Or add `"display": ":2"` to `~/.arcade-sim/config.json`.

---

## Windows — NSIS Installer

1. Download `arcade-fault-simulator_x.y.z_x64-setup.exe` from the Releases page.

2. Run the installer. Windows may show a SmartScreen prompt — click **More info → Run anyway** (the binary is self-signed for v1; code-signing certificate planned for v2).

3. The installer adds a Start Menu entry and a desktop shortcut. Launch **Arcade Fault Simulator**.

4. First-run asks for ROM directory. If bundled MAME is unavailable, the app
  prompts for a local MAME binary path.

### WebView2

Windows 11 ships WebView2. On Windows 10 it is delivered by Windows Update. If the app fails to start with a message about WebView2, install it manually from:
https://developer.microsoft.com/en-us/microsoft-edge/webview2/

### MAME on Windows

On Windows, MAME runs in a minimized window (not headless). The simulator captures its output via ffmpeg `gdigrab`. Keep the MAME window minimized — do not close it manually while the simulator is running.

---

## Configuration file

Both platforms share `~/.arcade-sim/config.json` (Linux) or `%USERPROFILE%\.arcade-sim\config.json` (Windows):

```json
{
  "mame_binary": "/usr/local/bin/mame",
  "rom_path": "/home/you/roms",
  "display": ":99"
}
```

All three keys can also be set via environment variables, which take precedence over the file:

| Key | Environment variable |
|-----|---------------------|
| `mame_binary` | `ARCADE_SIM_MAME_BINARY` |
| `rom_path` | `ARCADE_SIM_ROM_PATH` |
| `display` | `ARCADE_SIM_DISPLAY` |

`mame_binary` is optional when the bundled runtime is available.

---

## Stable vs Nightly

- **Stable** is the default release channel for end users.
- **Nightly** is an opt-in prerelease channel for testers.

Nightly builds use a separate app identifier and can be installed side-by-side
with stable. Use nightly only if you are comfortable with frequent updates and
occasional regressions.

---

## Building MAME from source

If you do not have a MAME binary, the quickest path on Linux:

```bash
sudo apt install git build-essential python3 libsdl2-dev libsdl2-ttf-dev \
    libfontconfig-dev libpulse-dev qtbase5-dev
git clone https://github.com/mamedev/mame.git
cd mame
make -j$(nproc) SUBTARGET=arcade SOURCES=src/mame/atari/centiped.cpp
# Binary produced at: ./mame
```

On Windows, see the MAME wiki: https://docs.mamedev.org/initialsetup/compilingmame.html

---

## Uninstalling

**Linux AppImage:** Delete the `.AppImage` file. Config stays at `~/.arcade-sim/`.

**Linux `.deb`:** `sudo dpkg -r arcade-fault-simulator`

**Windows:** Use Add/Remove Programs → *Arcade Fault Simulator*. Config stays at `%USERPROFILE%\.arcade-sim\`.

To also remove the config: delete `~/.arcade-sim/` (Linux) or `%USERPROFILE%\.arcade-sim\` (Windows).
