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
  gtkwave fd ripgrep
```
## Python venv
```bash
cd /home/jackie/arcade-sim
python -m venv .venv
source .venv/bin/activate
pip install pyparsing lark jsonschema
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
## Common errors
| Error                                                              | Cause                                                                 |
|--------------------------------------------------------------------|-----------------------------------------------------------------------|
| `Required files are missing, the machine cannot be run.`           | ROM set name mismatch (try `centiped3` for the rev-3 ROMs).           |
| `Input FB.GND already connected`                                   | Don't list `FB.GND` in `NET_C(GND, ...)`; `@GND` auto-connects.       |
| `tristate output FB.Y on device FB is connected to an analog net`  | Set `PARAM(FB.FORCE_TRISTATE_LOGIC, 0)` for analog tristate.          |
| `Unknown parameter FB.0`                                           | Macro substitution collision — rename the `-D` macro (avoid `MODE`).  |
| `make: Nothing to be done for ...`                                 | Wrong target; with this tree just run `make -j3 SOURCES=... TOOLS=1`. |
| `fatal: No names found, cannot describe anything.` during build    | Benign — shallow git clone has no tags. MAME embeds "unknown" in version. |
## Disk usage at end of Phase 1
- `vendor/mame/` (source + build):  about 7 GB
- `vendor/discrete/`:                ~1 MB
- `.venv/`:                          ~20 MB
- workspace tracked content:         <1 MB
