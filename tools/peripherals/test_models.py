#!/usr/bin/env python3
"""Unit tests for the peripheral models."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from models import (  # noqa: E402
    Button,
    CoinMech,
    HarnessSegment,
    Marquee,
    PowerSupply,
    PeripheralRegistry,
)


# ---------- PSU ----------

def test_psu_default_rails_use_trim_pot():
    psu = PowerSupply()
    s = psu.state()
    assert s["fault"] == "NORMAL"
    assert s["trim_5v"] == 5.05
    assert s["rails"]["5V"] == 5.05
    assert s["ripple_mv_pp"] == 30.0


def test_psu_trim_pot_adjusts_5v_rail():
    psu = PowerSupply()
    psu.adjust("trim_5v", 5.25)
    assert psu.state()["rails"]["5V"] == 5.25


def test_psu_trim_pot_rejects_out_of_range():
    psu = PowerSupply()
    try:
        psu.adjust("trim_5v", 6.0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for trim_5v > 5.5")


def test_psu_failed_regulator_overrides_trim():
    psu = PowerSupply()
    psu.adjust("trim_5v", 4.6)  # operator dialed it down
    psu.apply_fault("failed_regulator")
    rails = psu.state()["rails"]
    assert rails["5V"] == 7.8  # pass element shorted; trim no longer in control


def test_psu_dried_cap_shows_ripple():
    psu = PowerSupply()
    psu.apply_fault("dried_filter_cap")
    s = psu.state()
    assert s["ripple_mv_pp"] >= 500


def test_psu_overload_trip_collapses_rails():
    psu = PowerSupply()
    psu.apply_fault("overload_trip")
    rails = psu.state()["rails"]
    assert all(v == 0.0 for v in rails.values())


def test_psu_clear_fault_returns_to_normal():
    psu = PowerSupply()
    psu.apply_fault("bad_rectifier")
    psu.clear_fault()
    assert psu.state()["fault"] == "NORMAL"


# ---------- coin mech ----------

def test_coin_mech_normal_accepts_coins():
    cm = CoinMech()
    cm.insert_coin()
    s = cm.state()
    assert s["credits"] == 1
    assert s["last_event"] == "accepted"


def test_coin_mech_jammed_rejects_all():
    cm = CoinMech()
    cm.apply_fault("jammed_mech")
    cm.insert_coin()
    s = cm.state()
    assert s["credits"] == 0
    assert s["last_event"] == "rejected"


def test_coin_mech_stuck_switch_streams_credits():
    cm = CoinMech()
    cm.apply_fault("stuck_switch")
    s1 = cm.state()
    s2 = cm.state()
    assert s2["credits"] > s1["credits"]


# ---------- buttons ----------

def test_button_fault_is_recorded():
    b = Button("BTN_X", "test")
    b.apply_fault("stuck_closed")
    s = b.state()
    assert s["fault"] == "stuck_closed"
    assert s["label"] == "test"


def test_button_rejects_unknown_fault():
    b = Button("BTN_X", "test")
    try:
        b.apply_fault("bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown fault")


# ---------- marquee ----------

def test_marquee_visible_state_changes_with_fault():
    m = Marquee()
    assert m.state()["visible_state"] == "on"
    m.apply_fault("dead_tube")
    assert m.state()["visible_state"] == "off"
    m.apply_fault("ballast_flicker")
    assert m.state()["visible_state"] == "flickering"
    m.apply_fault("aging_tube")
    assert m.state()["visible_state"] == "dim"


# ---------- harness ----------

def test_harness_records_endpoints():
    h = HarnessSegment("X", "A", "B")
    s = h.state()
    assert s["src"] == "A"
    assert s["dst"] == "B"


# ---------- registry ----------

def test_registry_lists_all_peripherals():
    reg = PeripheralRegistry()
    items = reg.all()
    types = {it["type"] for it in items}
    assert types == {"psu", "coin_mech", "button", "marquee", "harness"}
    # Three buttons, four harness segments, plus PSU+coin+marquee = 10.
    assert len(items) == 10


def test_registry_apply_fault_routes_to_target():
    reg = PeripheralRegistry()
    reg.apply_fault("PSU1", "sagging_mains")
    s = reg.find("PSU1").state()
    assert s["fault"] == "sagging_mains"


def test_registry_adjust_routes_to_target():
    reg = PeripheralRegistry()
    reg.adjust("PSU1", "trim_5v", 4.7)
    assert reg.find("PSU1").state()["trim_5v"] == 4.7


def test_registry_reset_all_clears_faults_and_restores_trim():
    reg = PeripheralRegistry()
    reg.apply_fault("PSU1", "sagging_mains")
    reg.adjust("PSU1", "trim_5v", 4.6)
    reg.apply_fault("MARQ1", "dead_tube")
    reg.reset_all()
    assert reg.find("PSU1").state()["fault"] == "NORMAL"
    assert reg.find("PSU1").state()["trim_5v"] == 5.05
    assert reg.find("MARQ1").state()["fault"] == "NORMAL"


def test_registry_unknown_id_raises():
    reg = PeripheralRegistry()
    try:
        reg.apply_fault("NOPE", "open")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown peripheral")


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
