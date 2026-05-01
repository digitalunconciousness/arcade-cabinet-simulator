#!/usr/bin/env python3
# license:CC0-1.0
"""
Behavioral models for cabinet-level peripherals.

These are stateful Python objects (no netlist solver involvement). Each
model exposes:
  - state(): a JSON-serializable dict of current values for the UI
  - apply_fault(name): activate a named fault category
  - clear_fault(): return to NORMAL
  - adjust(param, value): set a tunable parameter (e.g., the PSU trim pot)
  - SUPPORTED_FAULTS / SUPPORTED_PARAMS: declarative lists for the manifest

Together with the netlist-side FAULT_BUFFER work and the MAME bridge,
this is the third surface the cabinet-bus speaks to.
"""

from __future__ import annotations

from typing import Optional

from audio import AudioChain
from crt import CRTChassis
from trackball import Trackball


# ---------- power supply ----------

class PowerSupply:
    """Arcade switching/linear PSU with adjustable 5V trim and fault modes.

    Real-cabinet behavior: the +5V rail has a trim pot the operator turns
    to compensate for voltage drop in the harness or sag under load. The
    pot's range is ~4.5V to 5.5V; sweet spot is 5.05V at the PCB. When
    something else fails (bad cap, harness corrosion), operators tend to
    crank the pot to mask it; that compensates short-term but stresses
    TTL chips when the underlying fault is later fixed.

    Fault modes are independent of the trim adjustment, but the resulting
    rail voltage at the PCB is a function of both.
    """

    SUPPORTED_FAULTS = [
        "bad_rectifier",      # half-wave operation; rail drops ~30% with massive ripple
        "dried_filter_cap",   # high ripple superimposed on rail
        "failed_regulator",   # 5V floats up to ~7-8V or sags to ~3V
        "sagging_mains",      # all rails proportionally low (brown-out)
        "overload_trip",      # rail collapses; usually shut-down state
    ]

    SUPPORTED_PARAMS = {
        "trim_5v": {"min": 4.5, "max": 5.5, "default": 5.05, "step": 0.01},
    }

    NORMAL_RAILS = {"5V": 5.05, "12V": 12.0, "-5V": -5.0}

    def __init__(self, ident: str = "PSU1"):
        self.id = ident
        self.fault: Optional[str] = None
        self.trim_5v: float = 5.05
        self.load_factor: float = 1.0   # 0..1, how heavy the PCB+lights+monitor are pulling

    # --- interface ---

    def apply_fault(self, name: str) -> None:
        if name not in self.SUPPORTED_FAULTS and name != "":
            raise ValueError(f"unknown PSU fault: {name!r}")
        self.fault = name or None

    def clear_fault(self) -> None:
        self.fault = None

    def adjust(self, param: str, value: float) -> None:
        spec = self.SUPPORTED_PARAMS.get(param)
        if spec is None:
            raise ValueError(f"unknown PSU param: {param!r}")
        v = float(value)
        if not (spec["min"] <= v <= spec["max"]):
            raise ValueError(
                f"{param}={v} out of range [{spec['min']}..{spec['max']}]"
            )
        setattr(self, param, v)

    def state(self) -> dict:
        return {
            "id": self.id,
            "type": "psu",
            "fault": self.fault or "NORMAL",
            "trim_5v": self.trim_5v,
            "rails": self._rails(),
            "ripple_mv_pp": self._ripple_mv_pp(),
            "supported_faults": self.SUPPORTED_FAULTS,
            "supported_params": self.SUPPORTED_PARAMS,
        }

    # --- internals ---

    def _rails(self) -> dict:
        rails = dict(self.NORMAL_RAILS)
        rails["5V"] = self.trim_5v   # trim takes effect even with no fault
        f = self.fault
        if f == "bad_rectifier":
            # Half-wave; the regulator can't keep up under load.
            rails["5V"] = round(self.trim_5v * 0.7, 3)
            rails["12V"] = round(rails["12V"] * 0.7, 3)
        elif f == "dried_filter_cap":
            # DC mean is fine; ripple shows up in `_ripple_mv_pp`.
            pass
        elif f == "failed_regulator":
            # Pass-element shorted: rail floats up to ~7.8V.
            rails["5V"] = 7.8
        elif f == "sagging_mains":
            scale = 0.85
            rails = {k: round(v * scale, 3) for k, v in rails.items()}
            rails["5V"] = round(self.trim_5v * scale, 3)
        elif f == "overload_trip":
            rails = {k: 0.0 for k in rails}
        return rails

    def _ripple_mv_pp(self) -> float:
        if self.fault == "dried_filter_cap":
            return round(800.0 * self.load_factor, 1)
        if self.fault == "bad_rectifier":
            return round(1800.0 * self.load_factor, 1)
        return 30.0  # healthy ripple on a well-filtered rail


# ---------- coin mech ----------

class CoinMech:
    """Atari-style coin mechanism state machine.

    Real states cycle: idle -> coin_detected -> validating -> accept|reject.
    Faults change observable behavior for the player.
    """

    SUPPORTED_FAULTS = [
        "stuck_switch",   # free credits — switch reads coin-present forever
        "dirty_contact",  # intermittent acceptance
        "jammed_mech",    # rejects everything
        "miscalibrated",  # accepts wrong denominations
    ]

    SUPPORTED_PARAMS = {}

    def __init__(self, ident: str = "COIN1"):
        self.id = ident
        self.fault: Optional[str] = None
        self.credits: int = 0
        self.last_event: Optional[str] = None  # idle | accepted | rejected

    def apply_fault(self, name: str) -> None:
        if name not in self.SUPPORTED_FAULTS and name != "":
            raise ValueError(f"unknown coin fault: {name!r}")
        self.fault = name or None

    def clear_fault(self) -> None:
        self.fault = None

    def adjust(self, param: str, value) -> None:
        raise ValueError(f"coin mech has no adjustable params (got {param!r})")

    def insert_coin(self) -> None:
        """Simulate a coin drop. Outcome depends on fault state."""
        f = self.fault
        if f == "jammed_mech":
            self.last_event = "rejected"
        elif f == "miscalibrated":
            # Half-credit: every two coins yield one credit.
            self.credits += 1
            if self.credits % 2 == 1:
                self.last_event = "accepted"
            else:
                self.last_event = "rejected"
        else:
            self.last_event = "accepted"
            self.credits += 1

    def state(self) -> dict:
        # stuck_switch streams credits constantly.
        if self.fault == "stuck_switch":
            self.credits += 1
            self.last_event = "accepted"
        return {
            "id": self.id,
            "type": "coin_mech",
            "fault": self.fault or "NORMAL",
            "credits": self.credits,
            "last_event": self.last_event or "idle",
            "supported_faults": self.SUPPORTED_FAULTS,
            "supported_params": self.SUPPORTED_PARAMS,
        }


# ---------- button ----------

class Button:
    """A single panel button. Faults reflect contact failures."""

    SUPPORTED_FAULTS = [
        "stuck_closed",    # always-pressed
        "stuck_open",      # never registers
        "intermittent",    # registers ~50% of presses
        "bouncy",          # contact bounce produces phantom double-presses
        "slow_release",    # mechanical sluggishness; long debounce
    ]

    SUPPORTED_PARAMS = {}

    def __init__(self, ident: str, label: str):
        self.id = ident
        self.label = label
        self.fault: Optional[str] = None

    def apply_fault(self, name: str) -> None:
        if name not in self.SUPPORTED_FAULTS and name != "":
            raise ValueError(f"unknown button fault: {name!r}")
        self.fault = name or None

    def clear_fault(self) -> None:
        self.fault = None

    def adjust(self, param: str, value) -> None:
        raise ValueError(f"button has no adjustable params (got {param!r})")

    def state(self) -> dict:
        return {
            "id": self.id,
            "type": "button",
            "label": self.label,
            "fault": self.fault or "NORMAL",
            "supported_faults": self.SUPPORTED_FAULTS,
            "supported_params": self.SUPPORTED_PARAMS,
        }


# ---------- marquee ----------

class Marquee:
    """Fluorescent-tube marquee with ballast. Faults match real-world wear."""

    SUPPORTED_FAULTS = [
        "dead_tube",          # no light
        "ballast_slow_start", # 5-30 second flicker before catching
        "ballast_flicker",    # continuous ~3 Hz strobe
        "ballast_hum",        # acoustic noise but light is fine
        "aging_tube",         # dim, color-shifted toward brown
    ]

    SUPPORTED_PARAMS = {}

    def __init__(self, ident: str = "MARQ1"):
        self.id = ident
        self.fault: Optional[str] = None

    def apply_fault(self, name: str) -> None:
        if name not in self.SUPPORTED_FAULTS and name != "":
            raise ValueError(f"unknown marquee fault: {name!r}")
        self.fault = name or None

    def clear_fault(self) -> None:
        self.fault = None

    def adjust(self, param: str, value) -> None:
        raise ValueError(f"marquee has no adjustable params (got {param!r})")

    def state(self) -> dict:
        f = self.fault
        if f == "dead_tube" or f == "ballast_slow_start":
            visible = "off"
        elif f == "ballast_flicker":
            visible = "flickering"
        elif f == "aging_tube":
            visible = "dim"
        else:
            visible = "on"
        return {
            "id": self.id,
            "type": "marquee",
            "fault": f or "NORMAL",
            "visible_state": visible,
            "supported_faults": self.SUPPORTED_FAULTS,
            "supported_params": self.SUPPORTED_PARAMS,
        }


# ---------- harness segment ----------

class HarnessSegment:
    """One length of wiring between two endpoints (e.g., PSU<->PCB)."""

    SUPPORTED_FAULTS = [
        "open",             # broken wire; downstream subsystem dies
        "short_to_gnd",     # often catastrophic
        "short_to_5v",      # also bad; can damage CMOS pins
        "high_resistance",  # corroded molex pin; rail droops, intermittent
        "chafed",           # intermittent open under vibration
    ]

    SUPPORTED_PARAMS = {}

    def __init__(self, ident: str, src: str, dst: str):
        self.id = ident
        self.src = src
        self.dst = dst
        self.fault: Optional[str] = None

    def apply_fault(self, name: str) -> None:
        if name not in self.SUPPORTED_FAULTS and name != "":
            raise ValueError(f"unknown harness fault: {name!r}")
        self.fault = name or None

    def clear_fault(self) -> None:
        self.fault = None

    def adjust(self, param: str, value) -> None:
        raise ValueError(f"harness has no adjustable params (got {param!r})")

    def state(self) -> dict:
        return {
            "id": self.id,
            "type": "harness",
            "src": self.src,
            "dst": self.dst,
            "fault": self.fault or "NORMAL",
            "supported_faults": self.SUPPORTED_FAULTS,
            "supported_params": self.SUPPORTED_PARAMS,
        }


# ---------- registry ----------

class PeripheralRegistry:
    """Holds the cabinet's peripherals and routes commands to them.

    The Flask server creates one of these at startup and exposes its
    operations through `/api/peripherals/*`.
    """

    def __init__(self):
        self.psu = PowerSupply("PSU1")
        self.coin = CoinMech("COIN1")
        self.buttons = {
            b.id: b for b in [
                Button("BTN_START1", "1-Player Start"),
                Button("BTN_START2", "2-Player Start"),
                Button("BTN_FIRE",   "Fire"),
            ]
        }
        self.marquee = Marquee("MARQ1")
        self.crt = CRTChassis("CRT1", psu=self.psu)
        self.trackball = Trackball("TRACK1")
        self.audio = AudioChain("AUDIO1")
        self.harness = {
            h.id: h for h in [
                HarnessSegment("HARN_PSU_PCB",     "PSU",     "GamePCB"),
                HarnessSegment("HARN_PSU_MONITOR", "PSU",     "Monitor"),
                HarnessSegment("HARN_PSU_MARQUEE", "PSU",     "Marquee"),
                HarnessSegment("HARN_PCB_PANEL",   "GamePCB", "Panel"),
            ]
        }

    def all(self) -> list:
        out = [
            self.psu.state(),
            self.coin.state(),
            self.marquee.state(),
            self.crt.state(),
            self.trackball.state(),
            self.audio.state(),
        ]
        for b in self.buttons.values():
            out.append(b.state())
        for h in self.harness.values():
            out.append(h.state())
        return out

    def find(self, ident: str):
        if ident == self.psu.id:
            return self.psu
        if ident == self.coin.id:
            return self.coin
        if ident == self.crt.id:
            return self.crt
        if ident == self.trackball.id:
            return self.trackball
        if ident == self.audio.id:
            return self.audio
        if ident in self.buttons:
            return self.buttons[ident]
        if ident == self.marquee.id:
            return self.marquee
        if ident in self.harness:
            return self.harness[ident]
        return None

    def apply_fault(self, ident: str, fault: str) -> dict:
        target = self.find(ident)
        if target is None:
            raise ValueError(f"unknown peripheral: {ident!r}")
        target.apply_fault(fault)
        return target.state()

    def clear_fault(self, ident: str) -> dict:
        target = self.find(ident)
        if target is None:
            raise ValueError(f"unknown peripheral: {ident!r}")
        target.clear_fault()
        return target.state()

    def adjust(self, ident: str, param: str, value) -> dict:
        target = self.find(ident)
        if target is None:
            raise ValueError(f"unknown peripheral: {ident!r}")
        target.adjust(param, value)
        return target.state()

    def reset_all(self) -> None:
        for p in (self.psu, self.coin, self.marquee, self.crt, self.trackball, self.audio,
                  *self.buttons.values(), *self.harness.values()):
            p.clear_fault()
        self.psu.adjust("trim_5v", PowerSupply.SUPPORTED_PARAMS["trim_5v"]["default"])
        self.crt.adjust("brightness", CRTChassis.SUPPORTED_PARAMS["brightness"]["default"])
        self.crt.adjust("focus", CRTChassis.SUPPORTED_PARAMS["focus"]["default"])
        self.trackball.adjust("sensitivity", Trackball.SUPPORTED_PARAMS["sensitivity"]["default"])
        self.trackball.adjust("wear", Trackball.SUPPORTED_PARAMS["wear"]["default"])
        self.audio.adjust("master_gain", AudioChain.SUPPORTED_PARAMS["master_gain"]["default"])
        self.audio.adjust("hum_level", AudioChain.SUPPORTED_PARAMS["hum_level"]["default"])
        self.audio.adjust(
            "distortion_drive",
            AudioChain.SUPPORTED_PARAMS["distortion_drive"]["default"],
        )


__all__ = [
    "PowerSupply",
    "CoinMech",
    "Button",
    "Marquee",
    "CRTChassis",
    "Trackball",
    "AudioChain",
    "HarnessSegment",
    "PeripheralRegistry",
]
