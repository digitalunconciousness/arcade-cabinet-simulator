#!/usr/bin/env python3
"""Canonical board-agnostic schematic model.

Sits between the KiCad-specific parser (kicad_netlist.py) and the server
fault-routing layer. Serialises to/from JSON so the board package can persist
it without requiring KiCad to be installed at runtime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    from tools.schematic.kicad_netlist import SchematicModel as KicadModel, load_kicad_netlist  # server context
except ModuleNotFoundError:
    from kicad_netlist import SchematicModel as KicadModel, load_kicad_netlist  # type: ignore[no-redef]


@dataclass
class ComponentRecord:
    """One component in the canonical schematic."""
    ref: str
    chip_type: str          # value or part name, e.g. "74LS74", "4.7k"
    footprint: str
    lib: str
    description: str = ""   # free-text annotation (DP-182 sheet / comment)


@dataclass
class NetRecord:
    """One net in the canonical schematic."""
    name: str
    nodes: list[str]        # ["U8.1", "R12.2", ...]


@dataclass
class BoardSchematic:
    """Board-package-agnostic schematic model."""
    board_id: str
    revision: str
    source_file: str                        # original KiCad .net path
    components: dict[str, ComponentRecord]  # ref → ComponentRecord
    nets: dict[str, NetRecord]              # net_name → NetRecord

    def component_count(self) -> int:
        return len(self.components)

    def net_count(self) -> int:
        return len(self.nets)

    def nets_for_ref(self, ref: str) -> list[str]:
        """Return all net names that contain at least one node for *ref*."""
        return [
            name
            for name, net in self.nets.items()
            if any(node.startswith(f"{ref}.") for node in net.nodes)
        ]


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_from_kicad(
    kicad_model: KicadModel,
    board_id: str,
    revision: str = "1.0",
) -> BoardSchematic:
    """Convert a KiCad SchematicModel into a BoardSchematic."""
    components: dict[str, ComponentRecord] = {}
    for comp in kicad_model.components:
        chip_type = comp.part or comp.value or "UNKNOWN"
        components[comp.ref] = ComponentRecord(
            ref=comp.ref,
            chip_type=chip_type,
            footprint=comp.footprint,
            lib=comp.lib,
        )

    nets: dict[str, NetRecord] = {}
    for net in kicad_model.nets:
        nodes = [f"{n.ref}.{n.pin}" for n in net.nodes]
        nets[net.name] = NetRecord(name=net.name, nodes=nodes)

    return BoardSchematic(
        board_id=board_id,
        revision=revision,
        source_file=kicad_model.source,
        components=components,
        nets=nets,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_board(schematic: BoardSchematic, path: Path) -> None:
    """Serialise a BoardSchematic to JSON."""
    data = {
        "board_id": schematic.board_id,
        "revision": schematic.revision,
        "source_file": schematic.source_file,
        "components": {
            ref: asdict(comp)
            for ref, comp in schematic.components.items()
        },
        "nets": {
            name: {"name": net.name, "nodes": net.nodes}
            for name, net in schematic.nets.items()
        },
    }
    path.write_text(json.dumps(data, indent=2))


def load_board(path: Path) -> BoardSchematic:
    """Deserialise a BoardSchematic from JSON."""
    if not path.exists():
        raise FileNotFoundError(f"Board schematic not found: {path}")
    data = json.loads(path.read_text())
    components = {
        ref: ComponentRecord(**comp)
        for ref, comp in data["components"].items()
    }
    nets = {
        name: NetRecord(name=net["name"], nodes=net["nodes"])
        for name, net in data["nets"].items()
    }
    return BoardSchematic(
        board_id=data["board_id"],
        revision=data["revision"],
        source_file=data["source_file"],
        components=components,
        nets=nets,
    )


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Import a KiCad XML netlist into the canonical board schematic format."
    )
    parser.add_argument("netlist", help="Path to KiCad XML netlist (.net)")
    parser.add_argument("output", help="Output path for schematic.board.json")
    parser.add_argument("--board-id", default="unknown", help="Board identifier")
    parser.add_argument("--revision", default="1.0", help="Board revision")
    args = parser.parse_args()

    kicad = load_kicad_netlist(Path(args.netlist))
    board = import_from_kicad(kicad, board_id=args.board_id, revision=args.revision)
    save_board(board, Path(args.output))
    print(
        f"Saved {board.component_count()} components, {board.net_count()} nets"
        f" → {args.output}"
    )
