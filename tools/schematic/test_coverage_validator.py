"""
tests for tools/schematic/coverage_validator.py
"""

import json
import sys
from pathlib import Path

# Allow running directly: python tools/schematic/test_coverage_validator.py
sys.path.insert(0, str(Path(__file__).parent))

import coverage_validator as cv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_fault_map(tmp: Path, entries: list[dict]) -> None:
    fm = {"board_id": "test", "entries": entries}
    (tmp / "fault_map.json").write_text(json.dumps(fm))


def _write_scenario(scenarios_dir: Path, data: dict) -> None:
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    sid = data.get("id", "unknown")
    (scenarios_dir / f"{sid}.json").write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# _looks_like_fault_target
# ---------------------------------------------------------------------------

def test_fb_prefix_is_fault_target():
    assert cv._looks_like_fault_target("FB_CLK_Q") is True


def test_refpin_notation_is_fault_target():
    assert cv._looks_like_fault_target("CLK.Q") is True


def test_file_path_is_not_fault_target():
    assert cv._looks_like_fault_target("tools/peripherals/crt.py:CRTChassis") is False


def test_colon_path_is_not_fault_target():
    assert cv._looks_like_fault_target("tools/cabinet_bus/server.py:/api/mame/stuck_byte") is False


# ---------------------------------------------------------------------------
# validate_coverage — happy path
# ---------------------------------------------------------------------------

def test_resolved_via_fault_device(tmp_path):
    scenarios_dir = tmp_path / "scenarios"
    _write_fault_map(tmp_path, [
        {"ref": "CLK", "pin": "Q", "fault_device": "FB_CLK_Q",
         "fault_type": "FAULT_BUFFER", "scenarios": ["sync-lock"]},
    ])
    _write_scenario(scenarios_dir, {
        "id": "sync-lock",
        "coverage": ["FB_CLK_Q"],
    })
    report = cv.validate_coverage(tmp_path, scenarios_dir)
    assert ("sync-lock", "FB_CLK_Q") in report.resolved
    assert report.unmapped == []
    assert report.ok


def test_resolved_via_refpin(tmp_path):
    scenarios_dir = tmp_path / "scenarios"
    _write_fault_map(tmp_path, [
        {"ref": "H_LO", "pin": "RC", "fault_device": "FB_H_LO_RC",
         "fault_type": "FAULT_BUFFER", "scenarios": []},
    ])
    _write_scenario(scenarios_dir, {
        "id": "vertical-collapse",
        "coverage": ["H_LO.RC"],
    })
    report = cv.validate_coverage(tmp_path, scenarios_dir)
    assert ("vertical-collapse", "FB_H_LO_RC") in report.resolved
    assert report.ok


def test_legacy_coverage_goes_to_unmapped(tmp_path):
    scenarios_dir = tmp_path / "scenarios"
    _write_fault_map(tmp_path, [])
    _write_scenario(scenarios_dir, {
        "id": "sync-lock",
        "coverage": ["tools/peripherals/crt.py:CRTChassis"],
    })
    report = cv.validate_coverage(tmp_path, scenarios_dir)
    assert ("sync-lock", "tools/peripherals/crt.py:CRTChassis") in report.unmapped
    assert report.resolved == []
    assert report.ok  # legacy coverage is not a hard error


# ---------------------------------------------------------------------------
# validate_coverage — broken fault_map back-references
# ---------------------------------------------------------------------------

def test_broken_fault_map_reference_detected(tmp_path):
    scenarios_dir = tmp_path / "scenarios"
    _write_fault_map(tmp_path, [
        {"ref": "CLK", "pin": "Q", "fault_device": "FB_CLK_Q",
         "fault_type": "FAULT_BUFFER",
         "scenarios": ["sync-lock", "no-such-scenario"]},
    ])
    _write_scenario(scenarios_dir, {"id": "sync-lock", "coverage": []})
    report = cv.validate_coverage(tmp_path, scenarios_dir)
    assert ("FB_CLK_Q", "no-such-scenario") in report.broken_refs
    assert not report.ok


def test_all_fault_map_refs_valid(tmp_path):
    scenarios_dir = tmp_path / "scenarios"
    _write_fault_map(tmp_path, [
        {"ref": "CLK", "pin": "Q", "fault_device": "FB_CLK_Q",
         "fault_type": "FAULT_BUFFER", "scenarios": ["sync-lock"]},
    ])
    _write_scenario(scenarios_dir, {"id": "sync-lock", "coverage": ["FB_CLK_Q"]})
    report = cv.validate_coverage(tmp_path, scenarios_dir)
    assert report.broken_refs == []
    assert report.ok


# ---------------------------------------------------------------------------
# validate_coverage — multiple entries, mixed coverage
# ---------------------------------------------------------------------------

def test_mixed_coverage_report(tmp_path):
    scenarios_dir = tmp_path / "scenarios"
    _write_fault_map(tmp_path, [
        {"ref": "CLK", "pin": "Q", "fault_device": "FB_CLK_Q",
         "fault_type": "FAULT_BUFFER", "scenarios": ["sync-lock"]},
        {"ref": "H_LO", "pin": "RC", "fault_device": "FB_H_LO_RC",
         "fault_type": "FAULT_BUFFER", "scenarios": ["vertical-collapse"]},
    ])
    _write_scenario(scenarios_dir, {
        "id": "sync-lock",
        "coverage": ["FB_CLK_Q", "tools/peripherals/crt.py:CRTChassis"],
    })
    _write_scenario(scenarios_dir, {
        "id": "vertical-collapse",
        "coverage": ["H_LO.RC"],
    })
    report = cv.validate_coverage(tmp_path, scenarios_dir)
    assert len(report.resolved) == 2
    assert len(report.unmapped) == 1
    assert report.ok


# ---------------------------------------------------------------------------
# Edge: empty scenarios directory
# ---------------------------------------------------------------------------

def test_empty_scenarios_dir(tmp_path):
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    _write_fault_map(tmp_path, [
        {"ref": "CLK", "pin": "Q", "fault_device": "FB_CLK_Q",
         "fault_type": "FAULT_BUFFER", "scenarios": []},
    ])
    report = cv.validate_coverage(tmp_path, scenarios_dir)
    assert report.ok


# ---------------------------------------------------------------------------
# Edge: missing fault_map.json raises FileNotFoundError
# ---------------------------------------------------------------------------

def test_missing_fault_map_raises(tmp_path):
    import pytest
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        cv.validate_coverage(tmp_path, scenarios_dir)


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
