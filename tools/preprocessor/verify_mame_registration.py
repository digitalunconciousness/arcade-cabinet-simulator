#!/usr/bin/env python3
"""Verify custom netlist devices are registered across MAME's 3-file pattern.

This catches drift where a device is added to one generated registration file
but missed in the others.
"""

from __future__ import annotations

import argparse
from pathlib import Path


REGISTRATION_FILES = {
    "netlist.lua": Path("scripts/src/netlist.lua"),
    "nld_devinc.h": Path("src/lib/netlist/generated/nld_devinc.h"),
    "lib_entries.hxx": Path("src/lib/netlist/generated/lib_entries.hxx"),
}

DEVICE_SOURCE_FILES = {
    "FAULT_BUFFER": Path("src/lib/netlist/devices/nld_fault_buffer.cpp"),
    "BAD_RAM_CELL": Path("src/lib/netlist/devices/nld_bad_ram_cell.cpp"),
}


def _token_candidates(device: str) -> tuple[str, str]:
    lower = device.lower()
    return (f"nld_{lower}", device)


def verify_registration(mame_root: Path, devices: list[str]) -> dict:
    """Return per-device registration status across the expected files."""
    report: dict[str, dict[str, bool]] = {}
    for device in devices:
        report[device] = {}
        tokens = _token_candidates(device)
        for logical_name, rel_path in REGISTRATION_FILES.items():
            path = mame_root / rel_path
            if not path.exists():
                report[device][logical_name] = False
                continue
            text = path.read_text(errors="ignore")
            report[device][logical_name] = any(tok in text for tok in tokens)
    return report


def verify_mode_contract(mame_root: Path, devices: list[str]) -> dict:
    """Check that each device source defines MODE constants for values 0..3."""
    report: dict[str, dict[str, bool]] = {}
    for device in devices:
        src = DEVICE_SOURCE_FILES.get(device)
        checks = {
            "source_exists": False,
            "mode_0": False,
            "mode_1": False,
            "mode_2": False,
            "mode_3": False,
        }
        if src is None:
            report[device] = checks
            continue
        path = mame_root / src
        if not path.exists():
            report[device] = checks
            continue
        checks["source_exists"] = True
        text = path.read_text(errors="ignore")
        checks["mode_0"] = "= 0;" in text and "MODE_" in text
        checks["mode_1"] = "= 1;" in text and "MODE_" in text
        checks["mode_2"] = "= 2;" in text and "MODE_" in text
        checks["mode_3"] = "= 3;" in text and "MODE_" in text
        report[device] = checks
    return report


def _all_present(report: dict) -> bool:
    for checks in report.values():
        if not all(checks.values()):
            return False
    return True


def _all_mode_contract_present(report: dict) -> bool:
    for checks in report.values():
        if not checks["source_exists"]:
            return False
        if not (checks["mode_0"] and checks["mode_1"] and checks["mode_2"] and checks["mode_3"]):
            return False
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_mame_registration",
        description="Validate custom netlist device registration consistency.",
    )
    parser.add_argument(
        "--mame-root",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "vendor" / "mame",
        help="Path to MAME source root",
    )
    parser.add_argument(
        "--devices",
        nargs="+",
        default=["FAULT_BUFFER", "BAD_RAM_CELL"],
        help="Device names to check",
    )
    args = parser.parse_args(argv)

    report = verify_registration(args.mame_root, args.devices)
    mode_report = verify_mode_contract(args.mame_root, args.devices)

    ok = True
    for device, checks in report.items():
        present = all(checks.values())
        ok = ok and present
        status = "OK" if present else "MISSING"
        print(f"{device}: {status}")
        for name, found in checks.items():
            mark = "yes" if found else "no"
            print(f"  - {name}: {mark}")

    print("\nMODE contract (expects constants for values 0..3):")
    mode_ok = True
    for device, checks in mode_report.items():
        present = checks["source_exists"] and checks["mode_0"] and checks["mode_1"] and checks["mode_2"] and checks["mode_3"]
        mode_ok = mode_ok and present
        status = "OK" if present else "MISSING"
        print(f"{device}: {status}")
        for name, found in checks.items():
            mark = "yes" if found else "no"
            print(f"  - {name}: {mark}")

    return 0 if (ok and mode_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
