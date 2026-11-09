#!/usr/bin/env python3
# license:CC0-1.0
"""List every fault the legacy app offers, read from the legacy sources.

Sources, all under the legacy checkout (a worktree of the ``legacy-tauri`` tag):
  - peripheral models: each class's SUPPORTED_FAULTS, on every instance the
    registry creates (tools/peripherals/)
  - schematic pins: boards/centipede/fault_map.json, modes 1-3 (stuck-hi,
    stuck-lo, open), in two server configurations: as shipped (no board
    package, which is how every launcher starts the server) and with the
    board package loaded
  - scenarios: tests/scenarios/*.json
  - the raw RAM commands the UI and demo script expose
  - the netlist waveform path (/api/run) for every manifest pin and mode

Each entry says which legacy HTTP call applies it, so the audit drives the
fault exactly the way the app does.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMATIC_MODES = {1: "stuck_hi", 2: "stuck_lo", 3: "open"}


def _peripheral_entries(legacy_root: Path) -> list[dict]:
    sys.path.insert(0, str(legacy_root / "tools" / "peripherals"))
    try:
        import models  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    registry = models.PeripheralRegistry()
    entries = []
    for state in registry.all():
        for fault in state["supported_faults"]:
            entries.append({
                "id": f"peripheral/{state['id']}/{fault}",
                "kind": "peripheral",
                "source": f"tools/peripherals ({state['type']})",
                "apply": {"method": "POST", "path": "/api/peripherals/fault",
                          "body": {"id": state["id"], "fault": fault}},
            })
    return entries


def _schematic_entries(legacy_root: Path) -> list[dict]:
    fault_map = json.loads((legacy_root / "boards/centipede/fault_map.json").read_text())
    entries = []
    for config in ("shipped", "board_package"):
        for row in fault_map["entries"]:
            for mode, label in SCHEMATIC_MODES.items():
                entries.append({
                    "id": f"schematic/{config}/{row['ref']}.{row['pin']}/{label}",
                    "kind": "schematic",
                    "config": config,
                    "source": "boards/centipede/fault_map.json",
                    "fault_device": row["fault_device"],
                    "apply": {"method": "POST", "path": "/api/schematic/fault/apply",
                              "body": {"ref": row["ref"], "pin": row["pin"], "mode": mode}},
                })
    return entries


def _scenario_entries(legacy_root: Path) -> list[dict]:
    entries = []
    for path in sorted((legacy_root / "tests/scenarios").glob("*.json")):
        scenario = json.loads(path.read_text())
        entries.append({
            "id": f"scenario/{scenario['id']}",
            "kind": "scenario",
            "source": f"tests/scenarios/{path.name}",
            "title": scenario.get("title", ""),
            "apply": {"method": "POST", "path": f"/api/scenarios/{scenario['id']}/apply", "body": {}},
        })
    return entries


def _raw_entries() -> list[dict]:
    # tools/demo-stuck-pixel.sh defaults: column 16, row 12, value 0xFF.
    return [
        {
            "id": "raw/stuck_byte/col16-row12-ff",
            "kind": "raw",
            "source": "tools/demo-stuck-pixel.sh, /api/mame/stuck_byte",
            "apply": {"method": "POST", "path": "/api/mame/stuck_byte",
                      "body": {"col": 16, "row": 12, "value": 255}},
        },
        {
            "id": "raw/poke_ram/0x0590-ff",
            "kind": "raw",
            "source": "/api/mame/poke_ram",
            "apply": {"method": "POST", "path": "/api/mame/poke_ram",
                      "body": {"addr": "0x0590", "value": 255}},
        },
    ]


def _netlist_entries(legacy_root: Path) -> list[dict]:
    manifest = json.loads((legacy_root / "build/instrumented/sync_generator.manifest.json").read_text())
    entries = [{
        "id": "netlist/sync_generator/normal",
        "kind": "netlist",
        "source": "build/instrumented/sync_generator.cpp via /api/run",
        "faults": {},
    }]
    for row in manifest:
        for mode, label in SCHEMATIC_MODES.items():
            entries.append({
                "id": f"netlist/sync_generator/{row['refdes']}.{row['pin']}/{label}",
                "kind": "netlist",
                "source": "build/instrumented/sync_generator.cpp via /api/run",
                "faults": {row["fault_device"]: mode},
            })
    return entries


def build_inventory(legacy_root: Path) -> list[dict]:
    legacy_root = legacy_root.resolve()
    return (
        _peripheral_entries(legacy_root)
        + _schematic_entries(legacy_root)
        + _scenario_entries(legacy_root)
        + _raw_entries()
        + _netlist_entries(legacy_root)
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("legacy_root", type=Path)
    args = parser.parse_args(argv)
    inventory = build_inventory(args.legacy_root)
    json.dump(inventory, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
