#!/usr/bin/env python3
"""Unit tests for cabinet_bus.server create_app wiring."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "peripherals"))

from models import PeripheralRegistry  # noqa: E402
from server import create_app, MANIFEST_VERSION  # noqa: E402


class StubMameClient:
    """Minimal stub used so tests never open sockets."""

    def get_state(self):
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
