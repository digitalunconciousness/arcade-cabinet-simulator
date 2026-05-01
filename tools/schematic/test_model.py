#!/usr/bin/env python3
"""Unit tests for tools/schematic/model.py."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent))

from kicad_netlist import load_kicad_netlist  # noqa: E402
from model import (  # noqa: E402
    import_from_kicad,
    save_board,
    load_board,
    BoardSchematic,
    ComponentRecord,
    NetRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_NETLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<export version="E">
  <components>
    <comp ref="U8">
      <value>74LS74</value>
      <footprint>DIP-14</footprint>
      <libsource lib="MAME" part="TTL_7474"/>
    </comp>
    <comp ref="R12">
      <value>4.7k</value>
      <footprint>R_Axial</footprint>
      <libsource lib="MAME" part="R"/>
    </comp>
  </components>
  <nets>
    <net code="1" name="/HSYNC">
      <node ref="U8" pin="1"/>
      <node ref="R12" pin="2"/>
    </net>
    <net code="2" name="GND">
      <node ref="U8" pin="7"/>
    </net>
  </nets>
</export>
"""


def _write_netlist(tmp_dir: Path) -> Path:
    p = tmp_dir / "test.net"
    p.write_text(_MINIMAL_NETLIST)
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestImportFromKicad(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)
        netlist_path = _write_netlist(self._tmp_path)
        kicad_model = load_kicad_netlist(netlist_path)
        self.board = import_from_kicad(kicad_model, board_id="test-board")

    def tearDown(self):
        self._tmp.cleanup()

    def test_component_count(self):
        self.assertEqual(self.board.component_count(), 2)

    def test_net_count(self):
        self.assertEqual(self.board.net_count(), 2)

    def test_component_chip_type_uses_part_name(self):
        self.assertEqual(self.board.components["U8"].chip_type, "TTL_7474")

    def test_component_chip_type_falls_back_to_value(self):
        # R12's part is "R", footprint is R_Axial
        self.assertEqual(self.board.components["R12"].chip_type, "R")

    def test_net_nodes_are_refpin_strings(self):
        nodes = self.board.nets["/HSYNC"].nodes
        self.assertIn("U8.1", nodes)
        self.assertIn("R12.2", nodes)

    def test_board_id_is_preserved(self):
        self.assertEqual(self.board.board_id, "test-board")

    def test_source_file_is_recorded(self):
        self.assertIn("test.net", self.board.source_file)

    def test_nets_for_ref_returns_matching_nets(self):
        nets = self.board.nets_for_ref("U8")
        self.assertIn("/HSYNC", nets)
        self.assertIn("GND", nets)

    def test_nets_for_ref_excludes_unrelated_components(self):
        nets = self.board.nets_for_ref("R12")
        self.assertNotIn("GND", nets)
        self.assertIn("/HSYNC", nets)


class TestSaveLoadRoundtrip(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)
        netlist_path = _write_netlist(self._tmp_path)
        kicad_model = load_kicad_netlist(netlist_path)
        self.original = import_from_kicad(kicad_model, board_id="rt-board", revision="2.1")

    def tearDown(self):
        self._tmp.cleanup()

    def test_roundtrip_component_count(self):
        path = self._tmp_path / "schematic.board.json"
        save_board(self.original, path)
        loaded = load_board(path)
        self.assertEqual(loaded.component_count(), self.original.component_count())

    def test_roundtrip_net_count(self):
        path = self._tmp_path / "schematic.board.json"
        save_board(self.original, path)
        loaded = load_board(path)
        self.assertEqual(loaded.net_count(), self.original.net_count())

    def test_roundtrip_board_id(self):
        path = self._tmp_path / "schematic.board.json"
        save_board(self.original, path)
        loaded = load_board(path)
        self.assertEqual(loaded.board_id, "rt-board")

    def test_roundtrip_revision(self):
        path = self._tmp_path / "schematic.board.json"
        save_board(self.original, path)
        loaded = load_board(path)
        self.assertEqual(loaded.revision, "2.1")

    def test_roundtrip_chip_type(self):
        path = self._tmp_path / "schematic.board.json"
        save_board(self.original, path)
        loaded = load_board(path)
        self.assertEqual(loaded.components["U8"].chip_type, "TTL_7474")

    def test_roundtrip_net_nodes(self):
        path = self._tmp_path / "schematic.board.json"
        save_board(self.original, path)
        loaded = load_board(path)
        self.assertIn("U8.1", loaded.nets["/HSYNC"].nodes)

    def test_saved_json_is_human_readable(self):
        path = self._tmp_path / "schematic.board.json"
        save_board(self.original, path)
        text = path.read_text()
        data = json.loads(text)
        self.assertIn("components", data)
        self.assertIn("nets", data)

    def test_load_raises_on_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            load_board(self._tmp_path / "nonexistent.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
