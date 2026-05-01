#!/usr/bin/env python3
"""KiCad XML netlist parser for schematic-aware fault mapping foundations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class Component:
    ref: str
    value: str
    footprint: str
    lib: str
    part: str


@dataclass(frozen=True)
class NetNode:
    ref: str
    pin: str


@dataclass(frozen=True)
class Net:
    code: str
    name: str
    nodes: tuple[NetNode, ...]


@dataclass(frozen=True)
class SchematicModel:
    source: str
    components: tuple[Component, ...]
    nets: tuple[Net, ...]


def load_kicad_netlist(path: Path) -> SchematicModel:
    """Load a KiCad XML netlist exported by Eeschema."""
    if not path.exists():
        raise FileNotFoundError(f"KiCad netlist not found: {path}")
    root = ET.fromstring(path.read_text())

    comps: list[Component] = []
    for comp in root.findall("./components/comp"):
        libsource = comp.find("libsource")
        comps.append(
            Component(
                ref=comp.get("ref", ""),
                value=(comp.findtext("value") or "").strip(),
                footprint=(comp.findtext("footprint") or "").strip(),
                lib=(libsource.get("lib", "") if libsource is not None else ""),
                part=(libsource.get("part", "") if libsource is not None else ""),
            )
        )

    nets: list[Net] = []
    for net in root.findall("./nets/net"):
        nodes: list[NetNode] = []
        for node in net.findall("node"):
            nodes.append(NetNode(ref=node.get("ref", ""), pin=node.get("pin", "")))
        nets.append(
            Net(
                code=net.get("code", ""),
                name=net.get("name", ""),
                nodes=tuple(nodes),
            )
        )

    return SchematicModel(source=str(path), components=tuple(comps), nets=tuple(nets))


def summarize_model(model: SchematicModel) -> dict:
    """Return JSON-safe summary for API responses."""
    comp_types: dict[str, int] = {}
    for c in model.components:
        key = c.part or c.value or "UNKNOWN"
        comp_types[key] = comp_types.get(key, 0) + 1

    sorted_types = sorted(comp_types.items(), key=lambda kv: (-kv[1], kv[0]))
    top_types = [{"chip_type": k, "count": v} for k, v in sorted_types[:20]]

    return {
        "source": model.source,
        "component_count": len(model.components),
        "net_count": len(model.nets),
        "top_chip_types": top_types,
        "components": [
            {
                "ref": c.ref,
                "value": c.value,
                "footprint": c.footprint,
                "lib": c.lib,
                "part": c.part,
            }
            for c in model.components
        ],
    }


def find_component(model: SchematicModel, ref: str) -> Optional[Component]:
    """Lookup helper used by future UI endpoints."""
    for comp in model.components:
        if comp.ref == ref:
            return comp
    return None
