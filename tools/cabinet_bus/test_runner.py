#!/usr/bin/env python3
"""Unit tests for the cabinet-bus runner."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from runner import (  # noqa: E402
    MODE_LABELS,
    build_scenario,
    waveforms_to_json,
    _is_safe_identifier,
    _parse_log,
)


def test_modes_match_device_constants():
    assert MODE_LABELS[0] == "NORMAL"
    assert MODE_LABELS[1] == "STUCK_HI"
    assert MODE_LABELS[2] == "STUCK_LO"
    assert MODE_LABELS[3] == "OPEN"


def test_build_scenario_no_faults_is_passthrough():
    template = "NETLIST_START(main)\n{\n\tSOLVER(s,48000)\n}\n"
    assert build_scenario(template, {}) == template
    assert build_scenario(template, {"FB_X": 0}) == template  # NORMAL is no-op


def test_build_scenario_injects_param_before_closing_brace():
    template = "NETLIST_START(main)\n{\n\tSOLVER(s,48000)\n}\n"
    out = build_scenario(template, {"FB_V_LO_QC": 2})
    assert "PARAM(FB_V_LO_QC.MODE, 2)" in out
    # The injected block sits above the closing brace.
    assert out.index("PARAM(") < out.rindex("}")


def test_build_scenario_handles_multiple_faults():
    template = "NETLIST_START(main)\n{\n}\n"
    out = build_scenario(template, {"FB_A": 1, "FB_B": 3})
    assert "PARAM(FB_A.MODE, 1)" in out
    assert "PARAM(FB_B.MODE, 3)" in out


def test_build_scenario_rejects_injection_attempts():
    template = "NETLIST_START(main)\n{\n}\n"
    try:
        build_scenario(template, {"FB_X; rm -rf /": 1})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unsafe identifier")


def test_build_scenario_rejects_unknown_mode():
    template = "NETLIST_START(main)\n{\n}\n"
    try:
        build_scenario(template, {"FB_X": 99})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown mode")


def test_is_safe_identifier_accepts_plain_names():
    assert _is_safe_identifier("FB_V_LO_QC")
    assert _is_safe_identifier("HSYNC_n")
    assert _is_safe_identifier("X1")


def test_is_safe_identifier_rejects_bad_input():
    assert not _is_safe_identifier("")
    assert not _is_safe_identifier("FB X")
    assert not _is_safe_identifier("FB$X")
    assert not _is_safe_identifier("1FB")


def test_parse_log_handles_scientific_notation(tmp_path=None):
    # Hand-roll a tmp file because we don't want a pytest dependency.
    from tempfile import NamedTemporaryFile
    with NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write("0.000000000e+00 0.000000e+00\n")
        f.write("2.000000000e-10 1.000000e-01\n")
        f.write("# comment line that should be ignored\n")
        f.write("5.000000000e-04 3.999999e+00\n")
        path = f.name
    try:
        from pathlib import Path as _P
        out = _parse_log(_P(path))
        assert len(out) == 3
        assert out[0] == (0.0, 0.0)
        assert out[1][0] == 2e-10
        assert out[2][1] > 3.5
    finally:
        import os
        os.unlink(path)


def test_waveforms_to_json_uses_plain_lists():
    payload = waveforms_to_json({"X": [(0.0, 0.0), (1e-9, 4.0)]})
    assert payload == {"X": [[0.0, 0.0], [1e-9, 4.0]]}


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
