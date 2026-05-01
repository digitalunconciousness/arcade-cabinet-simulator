#!/usr/bin/env python3
# license:CC0-1.0
"""Behavioral trackball model for Phase 6.

Mouse-like deltas are transformed into quadrature-friendly pulse deltas.
Fault modes alter output in ways that mirror common field failures.
"""

from __future__ import annotations

from typing import Optional


class Trackball:
    SUPPORTED_FAULTS = [
        "dead_opto_x",
        "dead_opto_y",
        "dirty_roller",
        "seized_bearing",
        "failed_quadrature_phase",
        "encoder_cap_failure",
    ]

    SUPPORTED_PARAMS = {
        "sensitivity": {"min": 0.1, "max": 3.0, "default": 1.0, "step": 0.05},
        "wear": {"min": 0.0, "max": 1.0, "default": 0.0, "step": 0.01},
    }

    def __init__(self, ident: str = "TRACK1"):
        self.id = ident
        self.fault: Optional[str] = None
        self.sensitivity: float = 1.0
        self.wear: float = 0.0
        self.last_packet = {
            "dx": 0,
            "dy": 0,
            "quad_dx": 0,
            "quad_dy": 0,
        }

    def apply_fault(self, name: str) -> None:
        if name not in self.SUPPORTED_FAULTS and name != "":
            raise ValueError(f"unknown trackball fault: {name!r}")
        self.fault = name or None

    def clear_fault(self) -> None:
        self.fault = None

    def adjust(self, param: str, value: float) -> None:
        spec = self.SUPPORTED_PARAMS.get(param)
        if spec is None:
            raise ValueError(f"unknown trackball param: {param!r}")
        v = float(value)
        if not (spec["min"] <= v <= spec["max"]):
            raise ValueError(
                f"{param}={v} out of range [{spec['min']}..{spec['max']}]"
            )
        setattr(self, param, v)

    def apply_motion(self, dx: int, dy: int) -> dict:
        raw_x = int(round(float(dx) * self.sensitivity))
        raw_y = int(round(float(dy) * self.sensitivity))

        # Wear introduces overall drag before specific hard faults apply.
        drag = max(0.0, 1.0 - (self.wear * 0.7))
        x = int(round(raw_x * drag))
        y = int(round(raw_y * drag))

        if self.fault == "dead_opto_x":
            x = 0
        elif self.fault == "dead_opto_y":
            y = 0
        elif self.fault == "dirty_roller":
            # Alternate dropped bursts for repeatable intermittent output.
            if (abs(x) + abs(y)) % 2 == 0:
                x = int(round(x * 0.35))
                y = int(round(y * 0.35))
        elif self.fault == "seized_bearing":
            x = int(round(x * 0.25))
            y = int(round(y * 0.25))
        elif self.fault == "failed_quadrature_phase":
            x = -x
            y = -y
        elif self.fault == "encoder_cap_failure":
            # Bounce/noise: add small signed jitter tied to current motion.
            jx = 1 if x >= 0 else -1
            jy = 1 if y >= 0 else -1
            x += jx if x != 0 else 0
            y += jy if y != 0 else 0

        packet = {
            "dx": int(dx),
            "dy": int(dy),
            "quad_dx": x,
            "quad_dy": y,
            "fault": self.fault or "NORMAL",
        }
        self.last_packet = packet
        return packet

    def state(self) -> dict:
        return {
            "id": self.id,
            "type": "trackball",
            "fault": self.fault or "NORMAL",
            "sensitivity": self.sensitivity,
            "wear": self.wear,
            "last_packet": self.last_packet,
            "supported_faults": self.SUPPORTED_FAULTS,
            "supported_params": self.SUPPORTED_PARAMS,
        }
