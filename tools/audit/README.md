# Stage 0 truth audit

Runs every fault the legacy app offers against the live game, headless, and records whether the game's output
changed. The results are in `docs/FAULT_AUDIT.md`, and the raw evidence is in `evidence/stage0/`.

## How it works

1. `inventory.py` lists every fault from the legacy sources: peripheral models, the schematic fault map (as shipped,
   and with the board package loaded), the scenarios, the raw RAM commands and the netlist waveform path.
2. For each fault, `run_audit.py` starts MAME with the plugin a fresh checkout builds (`patches/0002`) and with
   `probe.lua` as the autoboot script. The probe hashes the screen every frame, saves RAM and the screen at checkpoints,
   and pauses the game at frame 600.
3. While MAME is paused, `worker.py` builds the legacy server (`create_app()` from a `legacy-tauri` worktree), applies
   the fault over HTTP the way the app does, sends the same input every run gets, waits one PSU-watcher tick, and resumes.
   Every plugin command and reply is logged. Resume requests the app makes on its own are held until then, so every
   fault lands on frame 600.
4. The run is compared with a baseline that went through the same steps without a fault. The baseline runs twice
   first, and the audit stops if the two differ anywhere.

Verdicts:

| verdict | meaning |
|---|---|
| `changes-game-output` | the screen, the game's own RAM or its resets differ from the baseline after injection |
| `injected-cells-only` | only the RAM cells the plugin itself writes differ |
| `rejected-by-plugin` | every command the fault sent was refused as unknown |
| `not-sent` | the fault sent nothing to MAME |
| `no-change` | sent, accepted, no observable effect |
| `standalone-only` | netlist path: changes an nltool waveform, never reaches the game |

## Run it

From the repo root, with MAME built (see `patches/README.md`) and a ROM set in `roms/`:

```bash
git worktree add ../acs-legacy legacy-tauri
pip install flask requests jsonschema pillow
python tools/audit/run_audit.py --legacy-root ../acs-legacy \
    --mame vendor/mame/mame --nltool vendor/mame/nltool \
    --rompath roms --romset centiped3 --out evidence/stage0
python -m pytest -q tools/audit/test_audit.py
```

One fault takes about 7 s, and the whole inventory about 17 minutes on 4 cores. `--only <text>` runs the entries whose id
contains that text.
