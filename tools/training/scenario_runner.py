#!/usr/bin/env python3
# license:CC0-1.0
"""
Scenario runner for the Arcade Cabinet Fault Simulator.

Loads JSON scenario files from tests/scenarios/, applies each fault in the
scenario via the cabinet-bus HTTP API, and reports the result. Also used by
the Flask server's /api/scenarios/* endpoints.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import requests


SCENARIOS_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "scenarios"
DEFAULT_BASE_URL = "http://127.0.0.1:5050"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_scenario(path: Path) -> dict:
    """Load and validate a single scenario JSON file."""
    data = json.loads(path.read_text())
    required = ("id", "title", "faults", "clear_faults")
    for key in required:
        if key not in data:
            raise ValueError(f"scenario {path.name}: missing required field {key!r}")
    return data


def load_all_scenarios(directory: Path = SCENARIOS_DIR) -> list[dict]:
    """Return all scenarios from *directory*, sorted by filename."""
    if not directory.exists():
        return []
    scenarios = []
    for path in sorted(directory.glob("*.json")):
        try:
            scenarios.append(load_scenario(path))
        except (ValueError, json.JSONDecodeError) as e:
            print(f"warning: skipping {path.name}: {e}", file=sys.stderr)
    return scenarios


def scenario_metadata(scenario: dict) -> dict:
    """Return the display-safe subset of a scenario (no fault details)."""
    return {
        "id":          scenario["id"],
        "title":       scenario["title"],
        "difficulty":  scenario.get("difficulty", 1),
        "subsystems":  scenario.get("subsystems", []),
        "backstory":   scenario.get("backstory", ""),
    }


# ---------------------------------------------------------------------------
# Applying faults
# ---------------------------------------------------------------------------

def apply_scenario(scenario: dict, base_url: str = DEFAULT_BASE_URL) -> dict:
    """Apply all faults in *scenario* by posting to the cabinet-bus server.

    Returns a result dict with per-fault outcomes.
    """
    results = []
    for fault in scenario["faults"]:
        result = _apply_fault(fault, base_url)
        results.append(result)
    return {
        "id":      scenario["id"],
        "applied": True,
        "faults":  results,
    }


def clear_scenario(scenario: dict, base_url: str = DEFAULT_BASE_URL) -> dict:
    """Clear all faults in *scenario*."""
    results = []
    for fault in scenario.get("clear_faults", []):
        result = _apply_fault(fault, base_url)
        results.append(result)
    return {
        "id":      scenario["id"],
        "cleared": True,
        "faults":  results,
    }


def _apply_fault(fault: dict, base_url: str) -> dict:
    """Dispatch a single fault entry to the correct API endpoint."""
    fault_type = fault.get("type", "peripheral")

    try:
        if fault_type == "peripheral":
            url = f"{base_url}/api/peripherals/fault"
            payload = {"id": fault["target"], "fault": fault["fault"]}
            r = requests.post(url, json=payload, timeout=3)
            return {"type": fault_type, "target": fault["target"],
                    "status": r.status_code, "ok": r.status_code == 200}

        elif fault_type == "mame_stuck_byte":
            url = f"{base_url}/api/mame/stuck_byte"
            raw_addr = fault["addr"]
            addr = int(raw_addr, 0) if isinstance(raw_addr, str) else int(raw_addr)
            payload = {"addr": addr, "value": fault["value"]}
            r = requests.post(url, json=payload, timeout=3)
            return {"type": fault_type, "addr": raw_addr,
                    "status": r.status_code, "ok": r.status_code in (200, 503)}

        elif fault_type == "mame_clear_stuck":
            url = f"{base_url}/api/mame/clear_stuck"
            r = requests.post(url, json={}, timeout=3)
            return {"type": fault_type,
                    "status": r.status_code, "ok": r.status_code in (200, 503)}

        elif fault_type == "crt_overlay":
            url = f"{base_url}/api/crt/apply"
            payload = {"effect": fault.get("effect", "normal"),
                       "brightness": fault.get("brightness", 1.0)}
            r = requests.post(url, json=payload, timeout=3)
            return {"type": fault_type,
                    "status": r.status_code, "ok": r.status_code in (200, 503)}

        else:
            return {"type": fault_type, "ok": False,
                    "error": f"unknown fault type: {fault_type!r}"}

    except requests.exceptions.ConnectionError as e:
        return {"type": fault_type, "ok": False, "error": f"connection error: {e}"}
    except requests.exceptions.Timeout:
        return {"type": fault_type, "ok": False, "error": "timeout"}


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(
        prog="scenario_runner",
        description="Apply or clear a named fault scenario via the cabinet bus.",
    )
    parser.add_argument("action", choices=["apply", "clear", "list"])
    parser.add_argument("scenario_id", nargs="?", help="scenario id (for apply/clear)")
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="cabinet-bus base URL")
    args = parser.parse_args(argv)

    scenarios = load_all_scenarios()

    if args.action == "list":
        for s in scenarios:
            m = scenario_metadata(s)
            stars = "★" * m["difficulty"]
            print(f"  [{m['id']}] {m['title']}  {stars}")
            print(f"    {m['backstory'][:80]}")
        return

    if not args.scenario_id:
        parser.error("scenario_id is required for apply/clear")

    match = next((s for s in scenarios if s["id"] == args.scenario_id), None)
    if match is None:
        print(f"error: scenario {args.scenario_id!r} not found", file=sys.stderr)
        sys.exit(1)

    if args.action == "apply":
        result = apply_scenario(match, args.url)
    else:
        result = clear_scenario(match, args.url)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
