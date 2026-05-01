# Phase 8 — Schematic board packages + training surfaces
**Status:** ✅ complete
**Goal:** Replace the ad hoc KiCad-only import path with a stable board-package format and ship the first real schematic-aware training surfaces: canonical board data, fault-map-backed pin selection, 2D schematic/PCB/probe views, and scoring hooks that are specific enough to teach Centipede faults.
**Estimate:** 8-12 weekends.

## Why this phase exists
- The Phase 7 vertical slice proves the cabinet fault loop, but the user still interacts with a prototype control surface, not a technician-facing board view.
- KiCad XML is useful for ingestion, but the runtime needs a stable board package (`board.json` + `schematic.board.json` + `fault_map.json`) that survives UI and packaging work.
- Training mode needs traceable fault coverage tied to real refdes/pin/net names rather than generic scenario metadata.

## Definition of done
1. The server can boot from a board package path and expose a schematic summary with mapped fault metadata.
2. The Centipede board package exists with canonical schematic JSON and a maintained fault map for the covered netlist sections.
3. The UI has first-class 2D navigation surfaces:
   - KiCad-derived schematic view
   - PCB-photo or board-overlay view
   - probe / inspect panel for selected component, net, and active faults
4. Training scenarios point at real board-package coverage targets and can score user actions against those targets.
5. Documentation exists for the full KiCad → board package → instrumented runtime workflow.

## Code deliverables
- `tools/schematic/model.py` — canonical board-agnostic schematic model.
- `tools/schematic/board_package.py` — loader/summarizer for board packages.
- `boards/centipede/board.json` — board metadata and file layout contract.
- `boards/centipede/schematic.board.json` — canonical schematic snapshot.
- `boards/centipede/fault_map.json` — ref.pin → runtime fault target mapping.
- `tools/cabinet_bus/server.py` — board-package-aware schematic endpoints.
- `ui/` updates for schematic, PCB, and probe surfaces.
- `docs/KICAD_WORKFLOW.md` — transcription and instrumentation workflow.

## Verification target
```bash
cd /home/jackie/arcade-sim
source .venv/bin/activate
python tools/schematic/test_kicad_netlist.py
python tools/schematic/test_model.py
python tools/schematic/test_board_package.py
python tools/cabinet_bus/test_server.py
```

## Completed in this phase
- `boards/centipede/schematic.board.json` — populated from the two instrumented MAME netlist sources (8 components, 17 nets). Placeholder replaced with real data.
- `boards/centipede/fault_map.json` — all 11 instrumented fault targets mapped (8 sync generator + 3 address decoder). Each entry includes description and scenario cross-references.
- `tools/schematic/coverage_validator.py` — bidirectional checker: scenario coverage → fault map and fault map `scenarios` arrays → scenario files. 12 unit tests, all passing.
- `ui/` — Board Inspector section added: three-panel component browser / PCB-grid overview / probe panel. Probe panel supports per-pin fault mode selection, apply, and clear wired to the real `/api/schematic/fault/*` endpoints.
- All 116 unit tests passing after these additions.

## What Phase 8 intentionally does not finish
- It does not remove the Flask server deployment model yet.
- It does not build the full 3D cabinet.
- It does not commit to physical parts selection or cabinet fabrication.

## Navigation
← Previous: [Phase 7 — Cabinet UI + training mode](Phase-7-Cabinet-UI-Training.md) ·
Next: [Phase 9 — Desktop productization](Phase-9-Desktop-Productization.md) →