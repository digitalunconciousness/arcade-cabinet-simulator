#!/usr/bin/env python3
"""Unit tests for cabinet_bus.server create_app wiring."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "peripherals"))

from models import PeripheralRegistry  # noqa: E402
from server import create_app, MANIFEST_VERSION  # noqa: E402


class StubMameClient:
    """Minimal stub used so tests never open sockets."""

    def get_state(self):
        raise ConnectionError("stub")

    def set_crt_fault(self, effect, brightness=1.0):
        raise ConnectionError("stub")

    def stuck_byte(self, addr, value, cpu="maincpu"):
        raise ConnectionError("stub")


def _make_runtime_files(tmp: Path) -> tuple[Path, Path, Path, Path]:
    template = tmp / "sync_generator.cpp"
    template.write_text("NETLIST_START(main)\n{\n\tSOLVER(s,48000)\n}\n")

    manifest = tmp / "sync_generator.manifest.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "fault_device": "FB_V_LO_QC",
                    "refdes": "U12",
                    "pin": "QC",
                }
            ]
        )
    )

    nltool = tmp / "nltool"
    nltool.write_text("#!/bin/sh\nexit 0\n")

    ui_dir = tmp / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    (ui_dir / "index.html").write_text("<html><body>ok</body></html>")
    (ui_dir / "app.js").write_text("console.log('ok');")

    return template, manifest, nltool, ui_dir


def _make_board_package(tmp: Path) -> Path:
    board_dir = tmp / "boards" / "demo"
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / "board.json").write_text(
        json.dumps(
            {
                "board_id": "demo-board",
                "revision": "1.0",
                "canonical_schematic": "schematic.board.json",
                "fault_map": "fault_map.json",
            }
        )
    )
    (board_dir / "schematic.board.json").write_text(
        json.dumps(
            {
                "board_id": "demo-board",
                "revision": "1.0",
                "source_file": "demo.net",
                "components": {
                    "U12": {
                        "ref": "U12",
                        "chip_type": "TTL_9316",
                        "footprint": "DIP-16",
                        "lib": "MAME",
                        "description": "sync counter",
                    }
                },
                "nets": {
                    "VSYNC": {
                        "name": "VSYNC",
                        "nodes": ["U12.QC"],
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
                        "ref": "U12",
                        "pin": "QC",
                        "net_name": "VSYNC",
                        "fault_device": "FB_V_LO_QC",
                        "fault_type": "FAULT_BUFFER",
                        "description": "Vertical sync divider output",
                    }
                ],
            }
        )
    )
    return board_dir / "board.json"


def test_manifest_contract_includes_version_and_modes():
    with TemporaryDirectory() as d:
        template, manifest_path, nltool, ui_dir = _make_runtime_files(Path(d))
        app = create_app(
            template_path=template,
            manifest_path=manifest_path,
            nltool_path=nltool,
            ui_dir=ui_dir,
            mame_client=StubMameClient(),
            peripheral_registry=PeripheralRegistry(),
            scenario_loader=lambda: [],
        )

        client = app.test_client()
        res = client.get("/api/manifest")
        assert res.status_code == 200
        payload = res.get_json()
        assert payload["manifest_version"] == MANIFEST_VERSION
        assert isinstance(payload["fault_targets"], list)
        assert isinstance(payload["log_nets"], list)
        assert isinstance(payload["modes"], dict)


def test_create_app_uses_injected_scenario_loader():
    with TemporaryDirectory() as d:
        template, manifest_path, nltool, ui_dir = _make_runtime_files(Path(d))
        scenarios = [
            {
                "id": "demo",
                "title": "Demo Scenario",
                "difficulty": 1,
                "subsystems": ["CRT"],
                "coverage": ["tests/netlist/fault_buffer_test.cpp"],
                "backstory": "demo",
                "faults": [],
                "clear_faults": [],
            }
        ]
        app = create_app(
            template_path=template,
            manifest_path=manifest_path,
            nltool_path=nltool,
            ui_dir=ui_dir,
            mame_client=StubMameClient(),
            peripheral_registry=PeripheralRegistry(),
            scenario_loader=lambda: scenarios,
        )

        client = app.test_client()
        res = client.get("/api/scenarios")
        assert res.status_code == 200
        payload = res.get_json()
        assert "scenarios" in payload
        assert len(payload["scenarios"]) == 1
        assert payload["scenarios"][0]["id"] == "demo"
        assert payload["scenarios"][0]["coverage"] == [
            "tests/netlist/fault_buffer_test.cpp"
        ]


def test_schematic_fault_apply_and_list():
    with TemporaryDirectory() as d:
        template, manifest_path, nltool, ui_dir = _make_runtime_files(Path(d))
        app = create_app(
            template_path=template,
            manifest_path=manifest_path,
            nltool_path=nltool,
            ui_dir=ui_dir,
            mame_client=StubMameClient(),
            peripheral_registry=PeripheralRegistry(),
            scenario_loader=lambda: [],
        )

        client = app.test_client()
        res = client.post(
            "/api/schematic/fault/apply",
            json={"refdes": "U12", "pin": "QC", "mode": 2},
        )
        assert res.status_code == 200
        payload = res.get_json()
        assert payload["fault_device"] == "FB_V_LO_QC"
        assert payload["mode"] == 2

        listed = client.get("/api/schematic/faults").get_json()
        assert listed["faults"]["FB_V_LO_QC"] == 2


def test_schematic_summary_uses_board_package_when_present():
    with TemporaryDirectory() as d:
        tmp = Path(d)
        template, manifest_path, nltool, ui_dir = _make_runtime_files(tmp)
        board_path = _make_board_package(tmp)
        app = create_app(
            template_path=template,
            manifest_path=manifest_path,
            nltool_path=nltool,
            ui_dir=ui_dir,
            mame_client=StubMameClient(),
            peripheral_registry=PeripheralRegistry(),
            scenario_loader=lambda: [],
            board_package_path=board_path,
        )

        client = app.test_client()
        res = client.get("/api/schematic/summary")
        assert res.status_code == 200
        payload = res.get_json()
        assert payload["board_id"] == "demo-board"
        assert payload["component_count"] == 1
        assert payload["mapped_fault_count"] == 1


def test_schematic_fault_apply_accepts_board_package_ref_field():
    with TemporaryDirectory() as d:
        tmp = Path(d)
        template, manifest_path, nltool, ui_dir = _make_runtime_files(tmp)
        board_path = _make_board_package(tmp)
        app = create_app(
            template_path=template,
            manifest_path=manifest_path,
            nltool_path=nltool,
            ui_dir=ui_dir,
            mame_client=StubMameClient(),
            peripheral_registry=PeripheralRegistry(),
            scenario_loader=lambda: [],
            board_package_path=board_path,
        )

        client = app.test_client()
        res = client.post(
            "/api/schematic/fault/apply",
            json={"ref": "U12", "pin": "QC", "mode": 3},
        )
        assert res.status_code == 200
        payload = res.get_json()
        assert payload["fault_device"] == "FB_V_LO_QC"
        assert payload["fault"]["net_name"] == "VSYNC"
        assert payload["mode"] == 3


def test_schematic_faults_are_merged_into_run_spec():
    with TemporaryDirectory() as d:
        template, manifest_path, nltool, ui_dir = _make_runtime_files(Path(d))
        app = create_app(
            template_path=template,
            manifest_path=manifest_path,
            nltool_path=nltool,
            ui_dir=ui_dir,
            mame_client=StubMameClient(),
            peripheral_registry=PeripheralRegistry(),
            scenario_loader=lambda: [],
        )
        client = app.test_client()

        # Set one schematic fault first.
        res = client.post(
            "/api/schematic/fault/apply",
            json={"refdes": "U12", "pin": "QC", "mode": 1},
        )
        assert res.status_code == 200

        captured = {}

        def fake_run(spec):
            captured["faults"] = dict(spec.faults)
            return SimpleNamespace(
                waveforms={"HSYNC_n": [], "VSYNC_n": []},
                duration_s=0.001,
                fault_mode_count=len([m for m in spec.faults.values() if m != 0]),
                stderr="",
            )

        with patch("server.runner.run", side_effect=fake_run):
            run_res = client.post("/api/run", json={"faults": {}})
            assert run_res.status_code == 200
            assert captured["faults"].get("FB_V_LO_QC") == 1


def test_run_ignores_malformed_manifest_rows():
    with TemporaryDirectory() as d:
        tmp = Path(d)
        template = tmp / "sync_generator.cpp"
        template.write_text("NETLIST_START(main)\n{\n\tSOLVER(s,48000)\n}\n")

        # Missing fault_device is malformed but should not crash /api/run.
        manifest_path = tmp / "sync_generator.manifest.json"
        manifest_path.write_text(json.dumps([{"refdes": "U1", "pin": "QA"}]))

        nltool = tmp / "nltool"
        nltool.write_text("#!/bin/sh\nexit 0\n")

        ui_dir = tmp / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        (ui_dir / "index.html").write_text("<html><body>ok</body></html>")
        (ui_dir / "app.js").write_text("console.log('ok');")

        app = create_app(
            template_path=template,
            manifest_path=manifest_path,
            nltool_path=nltool,
            ui_dir=ui_dir,
            mame_client=StubMameClient(),
            peripheral_registry=PeripheralRegistry(),
            scenario_loader=lambda: [],
        )
        client = app.test_client()

        with patch("server.runner.run") as fake_run:
            fake_run.return_value = SimpleNamespace(
                waveforms={"HSYNC_n": [], "VSYNC_n": []},
                duration_s=0.001,
                fault_mode_count=0,
                stderr="",
            )
            run_res = client.post("/api/run", json={"faults": {}})

        assert run_res.status_code == 200


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
