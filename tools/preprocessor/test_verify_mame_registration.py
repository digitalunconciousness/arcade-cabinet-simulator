#!/usr/bin/env python3
"""Unit tests for verify_mame_registration.py."""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

from verify_mame_registration import verify_registration  # noqa: E402
from verify_mame_registration import verify_mode_contract  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_verify_registration_all_present():
    with TemporaryDirectory() as d:
        root = Path(d)
        _write(root / "scripts/src/netlist.lua", "nld_fault_buffer nld_bad_ram_cell")
        _write(root / "src/lib/netlist/generated/nld_devinc.h", "FAULT_BUFFER BAD_RAM_CELL")
        _write(root / "src/lib/netlist/generated/lib_entries.hxx", "nld_fault_buffer nld_bad_ram_cell")

        report = verify_registration(root, ["FAULT_BUFFER", "BAD_RAM_CELL"])
        assert all(report["FAULT_BUFFER"].values())
        assert all(report["BAD_RAM_CELL"].values())


def test_verify_registration_detects_missing_file_token():
    with TemporaryDirectory() as d:
        root = Path(d)
        _write(root / "scripts/src/netlist.lua", "nld_fault_buffer")
        _write(root / "src/lib/netlist/generated/nld_devinc.h", "FAULT_BUFFER")
        _write(root / "src/lib/netlist/generated/lib_entries.hxx", "")

        report = verify_registration(root, ["FAULT_BUFFER"])
        assert report["FAULT_BUFFER"]["netlist.lua"] is True
        assert report["FAULT_BUFFER"]["nld_devinc.h"] is True
        assert report["FAULT_BUFFER"]["lib_entries.hxx"] is False


def test_verify_mode_contract_detects_all_modes():
    with TemporaryDirectory() as d:
        root = Path(d)
        _write(
            root / "src/lib/netlist/devices/nld_fault_buffer.cpp",
            """
            static constexpr int MODE_NORMAL = 0;
            static constexpr int MODE_STUCK_HI = 1;
            static constexpr int MODE_STUCK_LO = 2;
            static constexpr int MODE_OPEN = 3;
            """,
        )
        _write(
            root / "src/lib/netlist/devices/nld_bad_ram_cell.cpp",
            """
            static constexpr int MODE_NORMAL = 0;
            static constexpr int MODE_STUCK_HI = 1;
            static constexpr int MODE_STUCK_LO = 2;
            static constexpr int MODE_FLIP = 3;
            """,
        )

        report = verify_mode_contract(root, ["FAULT_BUFFER", "BAD_RAM_CELL"])
        assert report["FAULT_BUFFER"]["source_exists"] is True
        assert report["BAD_RAM_CELL"]["source_exists"] is True
        assert report["FAULT_BUFFER"]["mode_0"] is True
        assert report["FAULT_BUFFER"]["mode_1"] is True
        assert report["FAULT_BUFFER"]["mode_2"] is True
        assert report["FAULT_BUFFER"]["mode_3"] is True
        assert report["BAD_RAM_CELL"]["mode_3"] is True


def test_verify_mode_contract_detects_missing_mode_value():
    with TemporaryDirectory() as d:
        root = Path(d)
        _write(
            root / "src/lib/netlist/devices/nld_fault_buffer.cpp",
            """
            static constexpr int MODE_NORMAL = 0;
            static constexpr int MODE_STUCK_HI = 1;
            static constexpr int MODE_STUCK_LO = 2;
            """,
        )

        report = verify_mode_contract(root, ["FAULT_BUFFER"])
        assert report["FAULT_BUFFER"]["source_exists"] is True
        assert report["FAULT_BUFFER"]["mode_3"] is False


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
