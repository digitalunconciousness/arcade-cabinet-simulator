#!/usr/bin/env python3
# license:CC0-1.0
"""Behavioral audio-chain model for Phase 6.

Represents POKEY -> amp -> speaker as a lightweight fault-profile mapper.
The UI consumes filter parameters from state() and applies WebAudio effects.
"""

from __future__ import annotations

from typing import Optional


class AudioChain:
    SUPPORTED_FAULTS = [
        "dead_amp",
        "hum",
        "distortion",
        "blown_speaker",
    ]

    SUPPORTED_PARAMS = {
        "master_gain": {"min": 0.0, "max": 1.5, "default": 1.0, "step": 0.01},
        "hum_level": {"min": 0.0, "max": 0.3, "default": 0.05, "step": 0.01},
        "distortion_drive": {"min": 0.0, "max": 1.0, "default": 0.35, "step": 0.01},
    }

    def __init__(self, ident: str = "AUDIO1"):
        self.id = ident
        self.fault: Optional[str] = None
        self.master_gain: float = 1.0
        self.hum_level: float = 0.05
        self.distortion_drive: float = 0.35

    def apply_fault(self, name: str) -> None:
        if name not in self.SUPPORTED_FAULTS and name != "":
            raise ValueError(f"unknown audio fault: {name!r}")
        self.fault = name or None

    def clear_fault(self) -> None:
        self.fault = None

    def adjust(self, param: str, value: float) -> None:
        spec = self.SUPPORTED_PARAMS.get(param)
        if spec is None:
            raise ValueError(f"unknown audio param: {param!r}")
        v = float(value)
        if not (spec["min"] <= v <= spec["max"]):
            raise ValueError(
                f"{param}={v} out of range [{spec['min']}..{spec['max']}]"
            )
        setattr(self, param, v)

    def state(self) -> dict:
        cfg = {
            "gain": self.master_gain,
            "hum_hz": 60.0,
            "hum_gain": 0.0,
            "distortion_drive": 0.0,
            "speaker_lowpass_hz": 12000.0,
        }

        if self.fault == "dead_amp":
            cfg["gain"] = 0.0
        elif self.fault == "hum":
            cfg["hum_gain"] = self.hum_level
        elif self.fault == "distortion":
            cfg["distortion_drive"] = self.distortion_drive
        elif self.fault == "blown_speaker":
            cfg["speaker_lowpass_hz"] = 1200.0
            cfg["gain"] = min(cfg["gain"], 0.65)

        return {
            "id": self.id,
            "type": "audio_chain",
            "fault": self.fault or "NORMAL",
            "master_gain": self.master_gain,
            "hum_level": self.hum_level,
            "distortion_drive": self.distortion_drive,
            "filter_params": cfg,
            "supported_faults": self.SUPPORTED_FAULTS,
            "supported_params": self.SUPPORTED_PARAMS,
        }
