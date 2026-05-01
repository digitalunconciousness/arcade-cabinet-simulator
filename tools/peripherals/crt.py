#!/usr/bin/env python3
# license:CC0-1.0
"""Behavioral CRT chassis model for Phase 6.

This model stays intentionally chassis-level: it exposes fault categories
and a derived shader-effect profile the UI can render without needing to
simulate analog subcircuits.
"""

from __future__ import annotations

from typing import Optional


class CRTChassis:
    """Wells-Gardner style chassis model with fault categories.

    The model can optionally reference a PSU object to couple image
    brightness to live +5V rail conditions.
    """

    SUPPORTED_FAULTS = [
        "no_hv",
        "vertical_collapse",
        "horizontal_collapse",
        "weak_focus",
        "brightness_drift",
        "bad_deflection_caps",
        "dim_picture",
        "sync_lock_failure",
        "ringing_ghosting",
    ]

    SUPPORTED_PARAMS = {
        "brightness": {"min": 0.2, "max": 1.8, "default": 1.0, "step": 0.01},
        "focus": {"min": 0.0, "max": 1.0, "default": 1.0, "step": 0.01},
    }

    def __init__(self, ident: str = "CRT1", psu=None):
        self.id = ident
        self.fault: Optional[str] = None
        self.brightness: float = 1.0
        self.focus: float = 1.0
        self.psu = psu
        self._drift_phase: float = 0.0

    def apply_fault(self, name: str) -> None:
        if name not in self.SUPPORTED_FAULTS and name != "":
            raise ValueError(f"unknown CRT fault: {name!r}")
        self.fault = name or None

    def clear_fault(self) -> None:
        self.fault = None

    def adjust(self, param: str, value: float) -> None:
        spec = self.SUPPORTED_PARAMS.get(param)
        if spec is None:
            raise ValueError(f"unknown CRT param: {param!r}")
        v = float(value)
        if not (spec["min"] <= v <= spec["max"]):
            raise ValueError(
                f"{param}={v} out of range [{spec['min']}..{spec['max']}]"
            )
        setattr(self, param, v)

    def state(self) -> dict:
        # Slow deterministic drift the UI can use for the drift shader.
        self._drift_phase = (self._drift_phase + 0.04) % 6.283185307

        shader = self._shader_effect_name()
        effective = self._effective_brightness()
        sync_ok = self.fault != "sync_lock_failure"

        return {
            "id": self.id,
            "type": "crt",
            "fault": self.fault or "NORMAL",
            "brightness": self.brightness,
            "focus": self.focus,
            "effective_brightness": round(effective, 3),
            "drift_phase": round(self._drift_phase, 4),
            "sync_ok": sync_ok,
            "shader_effect": shader,
            "supported_faults": self.SUPPORTED_FAULTS,
            "supported_params": self.SUPPORTED_PARAMS,
        }

    def _psu_5v_scale(self) -> float:
        if self.psu is None:
            return 1.0
        rails = self.psu.state().get("rails", {})
        rail_5v = float(rails.get("5V", 5.05))
        if rail_5v <= 0.0:
            return 0.0
        return max(0.0, min(1.2, rail_5v / 5.05))

    def _effective_brightness(self) -> float:
        value = self.brightness * self._psu_5v_scale()
        if self.fault == "no_hv":
            value *= 0.05
        elif self.fault == "dim_picture":
            value *= 0.55
        return max(0.0, min(2.0, value))

    def _shader_effect_name(self) -> str:
        fault_to_shader = {
            None: "crt_normal",
            "no_hv": "crt_no_hv",
            "vertical_collapse": "crt_vertical_collapse",
            "horizontal_collapse": "crt_horizontal_collapse",
            "weak_focus": "crt_weak_focus",
            "brightness_drift": "crt_brightness_drift",
            "bad_deflection_caps": "crt_bad_deflection_caps",
            "dim_picture": "crt_dim_picture",
            "sync_lock_failure": "crt_sync_lock_failure",
            "ringing_ghosting": "crt_ringing_ghosting",
        }
        return fault_to_shader[self.fault]
