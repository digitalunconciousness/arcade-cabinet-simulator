# KiCad → Working Simulator Prototype

This document walks you through the end-to-end process of transcribing a board
section from a physical schematic into a fault-injectable simulation running
inside MAME. It is written for the Centipede PCB (DP-182) but the steps apply
to any future board.

---

## Prerequisites

| Tool | Minimum version | Check |
|------|-----------------|-------|
| KiCad | 7.0 | `kicad --version` |
| Python | 3.11 | `python --version` |
| MAME build toolchain | GCC 11 / Clang 14 | `make --version` |
| venv | (ships with Python) | `python -m venv --help` |

Activate the project venv before running any Python commands:

```bash
cd /home/jackie/arcade-sim
source .venv/bin/activate
```

---

## Stage 1 — Source materials

You need the original schematics before drawing anything.

**Centipede sources** (do not redistribute — source your own legal copy):

| Document | What it contains |
|----------|-----------------|
| Atari DP-182-01A / -01B | Schematics sheets 1–4 (CPU, RAM, ROMs, video) |
| Atari DP-182-02A / -02B | Schematics sheets 5–8 (sync, audio, PSU, I/O) |
| Atari TM-182 | Maintenance manual; has block diagram and chip list |
| Sean Riddle PCB scans (`seanriddle.com`) | High-res photos — use to verify physical pin adjacency for `FAULT_SHORT` |

Place the PDFs under `docs/centipede/` (gitignored) as described in
`wiki/References.md`.

**Before you draw a single wire**, read the relevant sheet in its entirety and
note:
- Every IC reference designator (e.g. `U8`, `Z80`, `E5`)
- Net names used on power rails (`+5V`, `GND`, `-5V`, `+12V`)
- How multi-sheet nets are connected (KiCad uses global labels for these)

---

## Stage 2 — Create a KiCad project

```
boards/
  centipede/            ← board package directory (already exists)
    kicad/
      centipede-sheet4-sync.kicad_pro
      centipede-sheet4-sync.kicad_sch
```

1. Open KiCad, choose **File → New Project** and target
   `boards/centipede/kicad/`.
2. Name the project after the sheet you are transcribing, e.g.
   `centipede-sheet4-sync`.
3. If you are transcribing multiple sheets, use **hierarchical sheets** — one
   `.kicad_sch` per original schematic page, one top-level sheet that ties
   them together via hierarchical pins.

**Project settings to configure once:**

- Schematic → Net Highlighting: enable
- Schematic → ERC: run after every session
- Symbol libraries: add `vendor/discrete/kicad/MAME.lib` (see Stage 3)

---

## Stage 3 — Symbol library setup

The MAME netlist uses its own symbol vocabulary. The project ships a
KiCad-compatible library that mirrors it.

```bash
# The library lives here:
ls vendor/discrete/kicad/MAME.lib
ls vendor/discrete/kicad/netlist.lib   # alternate name
```

Add it to KiCad:

1. **Preferences → Manage Symbol Libraries → Project-specific tab**
2. Click the folder icon and browse to `vendor/discrete/kicad/MAME.lib`
3. Set the nickname to `MAME`

Common symbols you will use:

| Symbol | Description |
|--------|-------------|
| `TTL_7400` | Quad NAND |
| `TTL_7474` | Dual D-Flip-Flop |
| `TTL_9316` | Synchronous 4-bit counter (Centipede sync chain) |
| `NE555` | Timer |
| `R` | Resistor (generic) |
| `C` | Capacitor (generic) |
| `POT` | Potentiometer |
| `FAULT_BUFFER` | Fault-injection probe — **do not place in KiCad**; added by the preprocessor |
| `BAD_RAM_CELL` | RAM fault device — **do not place in KiCad**; added by the preprocessor |

`FAULT_BUFFER` and `BAD_RAM_CELL` are runtime-only devices injected by
`tools/preprocessor/instrument.py`. Do **not** add them manually to the
schematic.

---

## Stage 4 — Draw the schematic

Follow the DP-182 sheets precisely. Key conventions:

### Net naming

| Convention | Example | Reason |
|------------|---------|--------|
| Match DP-182 exactly | `/HSYNC`, `PLAYER_1_UP` | `fault_map.json` uses DP-182 net names as canonical keys |
| Power rails use KiCad power symbols | `+5V`, `GND` | ERC expects these |
| Off-sheet connections use global labels | `+5V`, `VIDEO_DATA` | Matches MAME driver net names in `centiped.cpp` |
| Active-low signals use `/` prefix | `/RESET`, `/CS` | Matches DP-182 notation |

### Reference designator conventions

Use the original DP-182 refdes unchanged (e.g. `U8`, `R12`, `C44`). This
ensures `fault_map.json` entries survive schematic revisions.

### Pin numbering

Always use the datasheet/DP-182 pin number, **not** KiCad's internal pin
index. ERC will catch mismatches.

### Annotation

Run **Tools → Annotate Schematic** once after placing all symbols. Do not
re-annotate after `fault_map.json` is populated — it will invalidate the
mappings.

---

## Stage 5 — Export the KiCad netlist

KiCad Eeschema can export an XML netlist directly usable by
`tools/schematic/kicad_netlist.py`.

1. **Tools → Generate Netlist**
2. Choose **KiCad** format (`.xml`)
3. Save to `boards/centipede/` as `centipede-sheet4-sync.net`
4. Verify the file is valid XML:

```bash
python - <<'EOF'
from xml.etree import ElementTree as ET
ET.parse("boards/centipede/centipede-sheet4-sync.net")
print("XML OK")
EOF
```

---

## Stage 6 — Parse and inspect with the canonical model

The project has a two-layer schematic stack:

```
KiCad XML netlist (.net)
        │
        ▼
tools/schematic/kicad_netlist.py   → SchematicModel (KiCad-specific)
        │
        ▼
tools/schematic/model.py           → BoardSchematic  (canonical, board-agnostic)
        │
        ▼
boards/centipede/schematic.board.json  (persisted canonical model)
```

Parse and save the canonical model:

```bash
python - <<'EOF'
from pathlib import Path
from tools.schematic.kicad_netlist import load_kicad_netlist
from tools.schematic.model import import_from_kicad, save_board

kicad = load_kicad_netlist(Path("boards/centipede/centipede-sheet4-sync.net"))
board = import_from_kicad(kicad, board_id="centipede-sheet4-sync")
save_board(board, Path("boards/centipede/schematic.board.json"))
print(f"Saved {len(board.components)} components, {len(board.nets)} nets")
EOF
```

Inspect the summary:

```bash
python - <<'EOF'
from pathlib import Path
from tools.schematic.model import load_board
board = load_board(Path("boards/centipede/schematic.board.json"))
for ref, comp in sorted(board.components.items()):
    print(f"  {ref:8s}  {comp.chip_type}")
EOF
```

---

## Stage 7 — Run the preprocessor on MAME netlist source

The KiCad schematic tells you what the circuit looks like. The **MAME netlist
source** (`.cpp`) is what actually runs in simulation. The preprocessor rewrites
that source to add `FAULT_BUFFER` probes.

Locate the relevant MAME netlist source for your section. For the sync
generator, it is:

```
vendor/mame/src/lib/netlist/devices/nld_sync_generator.cpp
```

Run the instrumentation:

```bash
python tools/preprocessor/instrument.py \
    --input  vendor/mame/src/lib/netlist/devices/nld_sync_generator.cpp \
    --output build/instrumented/sync_generator.cpp \
    --manifest build/instrumented/sync_generator.manifest.json
```

Inspect the manifest — every row is a probe point the server can fault:

```bash
python -c "
import json, pathlib
m = json.loads(pathlib.Path('build/instrumented/sync_generator.manifest.json').read_text())
for e in m['entries'][:10]:
    print(e['refdes'], e['pin'], '->', e['fault_device'])
"
```

---

## Stage 8 — Verify MAME device registration

Custom devices (`FAULT_BUFFER`, `BAD_RAM_CELL`) must appear in three MAME files
or the build will silently omit them. Verify all registrations are present:

```bash
python - <<'EOF'
from pathlib import Path
from tools.preprocessor.verify_mame_registration import verify_registration, verify_mode_contract

mame = Path("vendor/mame")
devices = ["FAULT_BUFFER", "BAD_RAM_CELL"]

reg = verify_registration(mame, devices)
for dev, files in reg.items():
    for fname, found in files.items():
        status = "OK" if found else "MISSING"
        print(f"  {dev:20s}  {fname:30s}  {status}")

mode = verify_mode_contract(mame, devices)
for dev, ok in mode.items():
    print(f"  {dev:20s}  MODE contract  {'OK' if ok else 'MISSING'}")
EOF
```

If any line shows `MISSING`, apply the relevant patch from `patches/`:

```bash
cd vendor/mame
git apply ../../patches/0001-Add-FAULT_BUFFER-netlist-device-for-runtime-fault-in.patch
git apply ../../patches/0002-Add-cabinet_bus-plugin-socket-bridge-for-the-cabinet.patch
git apply ../../patches/0003-Add-BAD_RAM_CELL-netlist-device-for-cell-level-RAM-f.patch
```

Re-run the verification script after patching.

---

## Stage 9 — Build MAME

From the `vendor/mame/` directory:

```bash
cd vendor/mame
make SUBTARGET=arcade SOURCES=src/mame/atari/centiped.cpp -j$(nproc) 2>&1 | tee /tmp/mame-build.log
```

Build artifacts end up in `vendor/mame/`. The relevant binary is `vendor/mame/mame`.

Common build errors and fixes:

| Error | Cause | Fix |
|-------|-------|-----|
| `nld_fault_buffer.cpp: No such file` | Patch not applied | Apply patch 0001 |
| `FAULT_BUFFER redeclared` | Patch applied twice | `git apply --check` before applying |
| `undefined reference to nlwav_` | Build order issue | Clean and rebuild: `make clean` then rebuild |

After a successful build, confirm the binary runs:

```bash
vendor/mame/mame -listxml centiped 2>/dev/null | head -5
```

---

## Stage 10 — Populate `fault_map.json`

The `fault_map.json` file maps every faultable ref.pin to a simulation action.
It lives in the board package alongside the schematic.

Template format (`boards/centipede/fault_map.json`):

```json
{
  "board_id": "centipede-sheet4-sync",
  "entries": [
    {
      "ref": "U8",
      "pin": "1",
      "net_name": "/HSYNC",
      "fault_device": "FB_U8_1",
      "fault_type": "FAULT_BUFFER",
      "description": "74LS74 pin 1 — /HSYNC drive (sync loss)"
    },
    {
      "ref": "R12",
      "pin": "2",
      "net_name": "VIDEO_DATA",
      "fault_device": "FB_R12_2",
      "fault_type": "FAULT_BUFFER",
      "description": "Load resistor on video data bus"
    }
  ]
}
```

**How to populate it:**

1. Cross-reference the manifest from Stage 7 with the canonical model from
   Stage 6 — every `fault_device` in the manifest should have a row here.
2. For each entry, fill `net_name` from the KiCad schematic net name (Stage 4).
3. Add `description` from the DP-182 annotation or TM-182 chip list.
4. For RAM cells, use `fault_type: "BAD_RAM_CELL"` and add `stuck_byte` and
   `address_mask` fields.

Validate that every manifest entry has a `fault_map.json` row:

```bash
python - <<'EOF'
import json
from pathlib import Path

manifest = json.loads(Path("build/instrumented/sync_generator.manifest.json").read_text())
fault_map = json.loads(Path("boards/centipede/fault_map.json").read_text())
fm_keys = {f"{e['ref']}.{e['pin']}" for e in fault_map["entries"]}

missing = []
for entry in manifest["entries"]:
    key = f"{entry['refdes']}.{entry['pin']}"
    if key not in fm_keys:
        missing.append(key)

if missing:
    print("MISSING from fault_map.json:")
    for k in sorted(missing):
        print(f"  {k}")
else:
    print("All manifest entries are mapped.")
EOF
```

---

## Stage 11 — Start the server and verify the schematic API

Load the board package into the server and confirm the schematic API responds:

```bash
# Terminal 1 — start MAME (uses run-demo.sh or direct invocation)
tools/run-demo.sh &

# Terminal 2 — start the cabinet_bus server with schematic support
python -m tools.cabinet_bus.server \
  --board-package boards/centipede/board.json

# Terminal 3 — query the schematic API
curl -s http://localhost:5000/api/schematic/summary | python -m json.tool
curl -s http://localhost:5000/api/schematic/faults  | python -m json.tool
```

Apply a test fault and confirm it appears in `/api/run`:

```bash
curl -s -X POST http://localhost:5000/api/schematic/fault/apply \
  -H 'Content-Type: application/json' \
  -d '{"ref": "U8", "pin": "1", "mode": 1}' | python -m json.tool

# The fault should now appear merged into the run spec
curl -s http://localhost:5000/api/run | python -m json.tool | grep schematic_faults -A 10
```

Clear faults:

```bash
curl -s -X POST http://localhost:5000/api/schematic/fault/clear \
  -H 'Content-Type: application/json' \
  -d '{"ref": "U8", "pin": "1"}' | python -m json.tool
```

---

## Stage 12 — Run the training scenarios

With a working schematic-aware server, validate the fault scenarios that target
your new board section:

```bash
python tools/training/scenario_runner.py \
    tests/scenarios/09-sync-lock.json \
    --server http://localhost:5000
```

Cross-check the `coverage` field in the scenario JSON against the `fault_device`
names in your `fault_map.json` — every coverage entry should resolve to a known
fault point.

---

## Checklist — "Done" criteria for a board section

Before marking a schematic section complete:

- [ ] KiCad schematic drawn from DP-182 source, ERC passes with zero errors
- [ ] XML netlist exported to `boards/centipede/`
- [ ] Canonical model saved to `boards/centipede/schematic.board.json`
- [ ] MAME netlist source instrumented; manifest in `build/instrumented/`
- [ ] `verify_mame_registration.py` shows all OK
- [ ] MAME builds cleanly with patches applied
- [ ] `fault_map.json` populated; no manifest entries are unmapped
- [ ] `/api/schematic/summary` returns correct component and net counts
- [ ] `/api/schematic/fault/apply` and `/clear` round-trip cleanly
- [ ] At least one scenario in `tests/scenarios/` targets this section and its
     `coverage` array references real fault device names from the manifest
- [ ] All unit tests pass: `python tools/cabinet_bus/test_server.py`

---

## Troubleshooting quick-reference

| Symptom | Likely cause | Where to look |
|---------|-------------|---------------|
| `FileNotFoundError: KiCad netlist not found` | Wrong path to `.net` file | Stage 5 — verify export path |
| Component count is 0 | KiCad exported `Pcbnew` format instead of `KiCad` | Re-export, choose KiCad format |
| `verify_registration` shows MISSING | Patches not applied or build cache stale | Stage 8 + `make clean` |
| `/api/schematic/summary` returns `{"error": ...}` | Server started without `--board-package` / `CABINET_BOARD_PATH`, or the board package files are incomplete | Pass `--board-package boards/centipede/board.json` and confirm `schematic.board.json` + `fault_map.json` exist |
| Fault applied but `/api/run` shows no change | Board `fault_map.json` points at the wrong manifest device, or the manifest is out of date | Compare `fault_map.json` `fault_device` values to `build/instrumented/*.manifest.json` |
| MAME crashes on start with custom devices | MODE contract violated | Re-run `verify_mode_contract` |
