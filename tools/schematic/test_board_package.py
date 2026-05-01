#!/usr/bin/env python3
"""Unit tests for board package loading helpers."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from board_package import load_board_package, summarize_board_package  # noqa: E402


def _make_board_package(tmp_dir: Path) -> Path:
    board_dir = tmp_dir / "boards" / "demo"
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / "board.json").write_text(
        json.dumps(
            {
                "board_id": "demo-board",
                "revision": "1.2",
                "canonical_schematic": "schematic.board.json",
                "fault_map": "fault_map.json",
            }
        )
    )
    (board_dir / "schematic.board.json").write_text(
        json.dumps(
            {
                "board_id": "demo-board",
                "revision": "1.2",
                "source_file": "demo.net",
                "components": {
                    "U1": {
                        "ref": "U1",
                        "chip_type": "TTL_7474",
                        "footprint": "DIP-14",
                        "lib": "MAME",
                        "description": "flip-flop",
                    },
                    "R1": {
                        "ref": "R1",
                        "chip_type": "R",
                        "footprint": "R_Axial",
                        "lib": "Device",
                        "description": "pull-up",
                    },
                },
                "nets": {
                    "/HSYNC": {
                        "name": "/HSYNC",
                        "nodes": ["U1.1", "R1.2"],
                    }
                },
            }
        )
    )
    (board_dir / "fault_map.json").write_text(
        json.dumps(
            {
                "board_id": "demo-board",
                "entries": [
                    {
                        "ref": "U1",
                        "pin": "1",
                        "net_name": "/HSYNC",
                        "fault_device": "FB_U1_1",
                        "fault_type": "FAULT_BUFFER",
                        "description": "Horizontal sync output",
                    }
                ],
            }
        )
    )
    return board_dir / "board.json"


class TestBoardPackage(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)
        self.board_path = _make_board_package(self._tmp_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_load_board_package_reads_metadata(self):
        package = load_board_package(self.board_path)
        self.assertEqual(package.board_id, "demo-board")
        self.assertEqual(package.revision, "1.2")

    def test_load_board_package_reads_schematic(self):
        package = load_board_package(self.board_path)
        self.assertEqual(package.schematic.component_count(), 2)
        self.assertEqual(package.schematic.net_count(), 1)

    def test_load_board_package_reads_fault_map(self):
        package = load_board_package(self.board_path)
        self.assertEqual(len(package.fault_map), 1)
        self.assertEqual(package.fault_map[0].fault_device, "FB_U1_1")

    def test_summary_includes_counts_and_faults(self):
        package = load_board_package(self.board_path)
        summary = summarize_board_package(package)
        self.assertEqual(summary["component_count"], 2)
        self.assertEqual(summary["mapped_fault_count"], 1)
        self.assertEqual(summary["fault_map"][0]["net_name"], "/HSYNC")

    def test_summary_includes_component_nets(self):
        package = load_board_package(self.board_path)
        summary = summarize_board_package(package)
        component = next(c for c in summary["components"] if c["ref"] == "U1")
        self.assertEqual(component["nets"], ["/HSYNC"])


if __name__ == "__main__":
    unittest.main(verbosity=2)