#!/usr/bin/env python3
"""Board package loader for schematic-aware cabinet simulation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

try:
    from tools.schematic.model import BoardSchematic, load_board  # server context
except ModuleNotFoundError:
    from model import BoardSchematic, load_board  # type: ignore[no-redef]


@dataclass(frozen=True)
class FaultMapEntry:
    ref: str
    pin: str
    net_name: str
    fault_device: str
    fault_type: str
    description: str = ""

    def key(self) -> tuple[str, str]:
        return (self.ref, self.pin)


@dataclass(frozen=True)
class BoardPackage:
    root: Path
    board_path: Path
    board_id: str
    revision: str
    metadata: dict
    schematic: BoardSchematic
    fault_map: tuple[FaultMapEntry, ...]


def load_board_package(path: Path) -> BoardPackage:
    """Load board.json plus its canonical schematic and fault map."""
    board_path = path.resolve()
    if board_path.is_dir():
        board_path = board_path / "board.json"
    if not board_path.exists():
        raise FileNotFoundError(f"Board package not found: {board_path}")

    metadata = json.loads(board_path.read_text())
    root = board_path.parent

    schematic_rel = metadata.get("canonical_schematic", "schematic.board.json")
    fault_map_rel = metadata.get("fault_map", "fault_map.json")

    schematic = load_board(root / schematic_rel)

    fault_map_data = json.loads((root / fault_map_rel).read_text())
    entries = tuple(FaultMapEntry(**entry) for entry in fault_map_data.get("entries", []))

    return BoardPackage(
        root=root,
        board_path=board_path,
        board_id=str(metadata.get("board_id", schematic.board_id)),
        revision=str(metadata.get("revision", schematic.revision)),
        metadata=metadata,
        schematic=schematic,
        fault_map=entries,
    )


def summarize_board_package(package: BoardPackage) -> dict:
    """Return JSON-safe board-package summary for API responses."""
    chip_types: dict[str, int] = {}
    for component in package.schematic.components.values():
        chip_types[component.chip_type] = chip_types.get(component.chip_type, 0) + 1

    sorted_types = sorted(chip_types.items(), key=lambda item: (-item[1], item[0]))
    return {
        "board_id": package.board_id,
        "revision": package.revision,
        "source": package.schematic.source_file,
        "component_count": package.schematic.component_count(),
        "net_count": package.schematic.net_count(),
        "mapped_fault_count": len(package.fault_map),
        "top_chip_types": [
            {"chip_type": chip_type, "count": count}
            for chip_type, count in sorted_types[:20]
        ],
        "components": [
            {
                "ref": component.ref,
                "chip_type": component.chip_type,
                "footprint": component.footprint,
                "lib": component.lib,
                "description": component.description,
                "nets": package.schematic.nets_for_ref(component.ref),
            }
            for component in package.schematic.components.values()
        ],
        "fault_map": [
            {
                "ref": entry.ref,
                "pin": entry.pin,
                "net_name": entry.net_name,
                "fault_device": entry.fault_device,
                "fault_type": entry.fault_type,
                "description": entry.description,
            }
            for entry in package.fault_map
        ],
    }