#!/usr/bin/env python3
"""Unit tests for KiCad netlist parser foundations."""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

from kicad_netlist import find_component, load_kicad_netlist, summarize_model  # noqa: E402


SAMPLE_XML = """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<export>
  <components>
    <comp ref=\"U1\">
      <value>74LS161</value>
      <footprint>DIP-16</footprint>
      <libsource lib=\"74xx\" part=\"74LS161\"/>
    </comp>
    <comp ref=\"U2\">
      <value>74LS155</value>
      <footprint>DIP-16</footprint>
      <libsource lib=\"74xx\" part=\"74LS155\"/>
    </comp>
  </components>
  <nets>
    <net code=\"1\" name=\"/HSYNC\">
      <node ref=\"U1\" pin=\"15\"/>
      <node ref=\"U2\" pin=\"1\"/>
    </net>
  </nets>
</export>
"""


def test_load_kicad_netlist_counts_components_and_nets():
    with TemporaryDirectory() as d:
        p = Path(d) / "centipede.net"
        p.write_text(SAMPLE_XML)
        model = load_kicad_netlist(p)
        assert len(model.components) == 2
        assert len(model.nets) == 1
        assert model.nets[0].name == "/HSYNC"


def test_summarize_model_includes_chip_types():
    with TemporaryDirectory() as d:
        p = Path(d) / "centipede.net"
        p.write_text(SAMPLE_XML)
        model = load_kicad_netlist(p)
        summary = summarize_model(model)
        assert summary["component_count"] == 2
        assert summary["net_count"] == 1
        chip_types = [x["chip_type"] for x in summary["top_chip_types"]]
        assert "74LS155" in chip_types
        assert "74LS161" in chip_types


def test_find_component_returns_refdes_match():
    with TemporaryDirectory() as d:
        p = Path(d) / "centipede.net"
        p.write_text(SAMPLE_XML)
        model = load_kicad_netlist(p)
        u1 = find_component(model, "U1")
        assert u1 is not None
        assert u1.part == "74LS161"
        assert find_component(model, "U99") is None


if __name__ == "__main__":
    failed = 0
    for name in sorted(dir()):
        if name.startswith("test_"):
            fn = globals()[name]
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL  {name}: {e}")
    sys.exit(0 if failed == 0 else 1)
