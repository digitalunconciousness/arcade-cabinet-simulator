#!/usr/bin/env python3
"""Unit tests for the auto-instrumentation preprocessor."""

from __future__ import annotations

from instrument import (
    FaultEntry,
    fault_device_name,
    instrument,
    parse_net_c_args,
    is_pin_ref,
)


def test_parse_net_c_args_simple():
    assert parse_net_c_args("A, B, C") == ["A", "B", "C"]


def test_parse_net_c_args_with_whitespace_and_empties():
    assert parse_net_c_args("  A.1 ,  B.2  ,, ") == ["A.1", "B.2"]


def test_is_pin_ref_accepts_refdes_pin():
    assert is_pin_ref("R1.1") is True
    assert is_pin_ref("FB_X_Y.Y") is True
    assert is_pin_ref("CLK1.Q") is True


def test_is_pin_ref_rejects_bare_words():
    assert is_pin_ref("GND") is False
    assert is_pin_ref("VCC") is False
    assert is_pin_ref("foo") is False


def test_fault_device_name_is_stable():
    assert fault_device_name("R1", "1") == "FB_R1_1"
    assert fault_device_name("U7", "OUT") == "FB_U7_OUT"


def test_instrument_two_pin_net_c_inserts_fault_buffer():
    src = "NET_C(R1.1, U2.A)\n"
    result = instrument(src)
    assert "FAULT_BUFFER(FB_R1_1, R1.1)" in result.instrumented_cpp
    assert "NET_C(FB_R1_1.Y, U2.A)" in result.instrumented_cpp
    assert len(result.manifest) == 1
    entry = result.manifest[0]
    assert entry.refdes == "R1"
    assert entry.pin == "1"
    assert entry.fault_device == "FB_R1_1"


def test_instrument_skips_power_rails():
    # NET_C(GND, R1.2) should be left alone since GND is not a pin ref.
    src = "NET_C(GND, R1.2)\n"
    result = instrument(src)
    assert result.instrumented_cpp == src
    assert result.manifest == []


def test_instrument_whitelist_filters_pins():
    src = "NET_C(R1.1, U2.A)\nNET_C(R3.1, U4.A)\n"
    result = instrument(src, pin_whitelist={"R1.1"})
    assert "FAULT_BUFFER(FB_R1_1" in result.instrumented_cpp
    assert "FAULT_BUFFER(FB_R3_1" not in result.instrumented_cpp
    assert [e.fault_device for e in result.manifest] == ["FB_R1_1"]


def test_instrument_preserves_lines_with_more_than_two_pins():
    # Three-pin NET_C is a shared net; current scaffold leaves it alone.
    src = "NET_C(R1.1, U2.A, U3.A)\n"
    result = instrument(src)
    assert result.instrumented_cpp == src
    assert result.manifest == []


def test_manifest_entry_key():
    e = FaultEntry("R1", "1", "FB_R1_1", 42, "NET_C(R1.1, U2.A)")
    assert e.key() == "R1.1"


if __name__ == "__main__":
    import sys
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
