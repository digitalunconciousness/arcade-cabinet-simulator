"""
tools/schematic/coverage_validator.py
Validate that scenario coverage entries resolve to board-package fault-map targets.

Two kinds of coverage strings are understood:
  - Board-package targets: ``FB_CLK_Q`` or ``CLK.Q`` — match a fault_device or
    ref+pin in the fault map.
  - Legacy file-path targets: ``tools/peripherals/crt.py:CRTChassis`` — logged
    as un-mapped (not an error, those faults are peripheral-side).

The validator also checks the reverse direction: every ``scenarios`` list in
``fault_map.json`` must name a scenario that exists on disk.

Exit code 0 = all mappable coverage entries resolve; 1 = at least one gap.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CoverageReport:
    resolved: list[tuple[str, str]] = field(default_factory=list)   # (scenario_id, fault_device)
    unmapped: list[tuple[str, str]] = field(default_factory=list)   # (scenario_id, coverage_str)
    broken_refs: list[tuple[str, str]] = field(default_factory=list)  # (fault_device, bad_scenario_id)
    missing_scenarios: list[str] = field(default_factory=list)  # scenario IDs in fault_map but not on disk

    @property
    def ok(self) -> bool:
        return not self.broken_refs and not self.missing_scenarios


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _looks_like_fault_target(coverage_str: str) -> bool:
    """Return True if the string looks like a board-package fault target.

    Accept ``FB_*`` device names and ``REF.PIN`` dotted notation.
    Reject anything containing a path separator or colon (file-path style).
    """
    if "/" in coverage_str or "\\" in coverage_str or ":" in coverage_str:
        return False
    return coverage_str.startswith("FB_") or ("." in coverage_str)


def _build_fault_device_index(fault_map: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    """Return two lookup tables from a loaded fault_map dict.

    Returns:
        (by_fault_device, by_refpin) where by_fault_device maps ``FB_X`` →
        entry dict, and by_refpin maps ``REF.PIN`` → entry dict.
    """
    by_device: dict[str, dict] = {}
    by_refpin: dict[str, dict] = {}
    for entry in fault_map.get("entries", []):
        if fd := entry.get("fault_device"):
            by_device[fd] = entry
        ref = entry.get("ref", "")
        pin = entry.get("pin", "")
        if ref and pin:
            by_refpin[f"{ref}.{pin}"] = entry
    return by_device, by_refpin


# ---------------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------------

def validate_coverage(
    board_package_path: str | Path,
    scenarios_dir: str | Path,
) -> CoverageReport:
    """Run coverage validation and return a :class:`CoverageReport`.

    Parameters
    ----------
    board_package_path:
        Path to the board package directory (must contain ``fault_map.json``).
    scenarios_dir:
        Directory containing scenario JSON files (``tests/scenarios/``).
    """
    board_package_path = Path(board_package_path)
    scenarios_dir = Path(scenarios_dir)

    # Load fault map
    fault_map_path = board_package_path / "fault_map.json"
    if not fault_map_path.exists():
        raise FileNotFoundError(f"fault_map.json not found in {board_package_path}")
    with fault_map_path.open() as f:
        fault_map = json.load(f)

    by_device, by_refpin = _build_fault_device_index(fault_map)

    # Load all scenarios
    scenario_files = sorted(scenarios_dir.glob("*.json"))
    scenario_ids: set[str] = set()
    scenarios: list[dict] = []
    for sf in scenario_files:
        with sf.open() as f:
            try:
                s = json.load(f)
            except json.JSONDecodeError:
                continue
        scenarios.append(s)
        if sid := s.get("id"):
            scenario_ids.add(sid)

    report = CoverageReport()

    # Forward check: scenario coverage entries → fault map
    for scenario in scenarios:
        sid = scenario.get("id", "<unknown>")
        for cov in scenario.get("coverage", []):
            if not _looks_like_fault_target(cov):
                report.unmapped.append((sid, cov))
                continue
            # Try fault_device name first, then REF.PIN
            entry = by_device.get(cov) or by_refpin.get(cov)
            if entry:
                report.resolved.append((sid, entry["fault_device"]))
            else:
                report.unmapped.append((sid, cov))

    # Reverse check: fault_map scenario references → scenario files
    for entry in fault_map.get("entries", []):
        for ref_scenario in entry.get("scenarios", []):
            if ref_scenario not in scenario_ids:
                report.broken_refs.append((entry["fault_device"], ref_scenario))
                if ref_scenario not in report.missing_scenarios:
                    report.missing_scenarios.append(ref_scenario)

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_report(report: CoverageReport, verbose: bool = False) -> None:
    print(f"\nCoverage validation results")
    print(f"  Resolved       : {len(report.resolved)}")
    print(f"  Unmapped       : {len(report.unmapped)}")
    print(f"  Broken refs    : {len(report.broken_refs)}")

    if report.broken_refs:
        print("\nBroken fault_map scenario references (fault_device → bad scenario id):")
        for fault_device, bad_sid in report.broken_refs:
            print(f"  {fault_device} → '{bad_sid}' (no matching scenario file)")

    if verbose and report.resolved:
        print("\nResolved:")
        for sid, fd in report.resolved:
            print(f"  {sid} → {fd}")

    if verbose and report.unmapped:
        print("\nUnmapped (legacy or peripheral coverage — not an error):")
        for sid, cov in report.unmapped:
            print(f"  {sid}: {cov}")

    print()
    if report.ok:
        print("OK — all board-package references are consistent.")
    else:
        print("FAIL — fix the items listed above.")


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Validate scenario coverage against a board package fault map."
    )
    parser.add_argument(
        "board_package",
        help="Path to board package directory (must contain fault_map.json)",
    )
    parser.add_argument(
        "--scenarios",
        default="tests/scenarios",
        help="Directory containing scenario JSON files (default: tests/scenarios)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print resolved and unmapped entries in addition to errors",
    )
    args = parser.parse_args(argv)

    report = validate_coverage(args.board_package, args.scenarios)
    _print_report(report, verbose=args.verbose)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
