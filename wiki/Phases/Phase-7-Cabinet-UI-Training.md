# Phase 7 — Cabinet UI + scenario library + training mode
**Status:** 🚧 not started
**Goal:** Polish the v1 deliverable. A cabinet-cutaway UI replaces the
prototype dashboard, a scenario library drives random fault generation
for training, and a probe view exposes any net or rail as a live
waveform.
- **Cabinet view** — 2D cutaway illustration of a Centipede upright
  cabinet. Click into the monitor chassis, PSU, harness routing,
  trackball assembly, coin door, etc. Each component opens its
  fault-injection panel.
- **Schematic view** — KiCad SVG export with clickable components for
  PCB-level faults.
- **PCB-photo view** — hand-mapped clickable regions over a high-res
  photo of the freshly-refit board, sourced from `scans/centipede/`.
- **Probe view** — live waveform graphs from any selected net or rail.
- **Training mode** — JSON scenario library with realism-weighted
  random selection, scoring, hint/reveal. Initial library of ~20-30
  scenarios growing organically.
**Estimate:** 8–12 weekends per the project plan.
## Plan sketch
1. Replace the current dashboard with the cabinet-cutaway layout.
2. Generate a KiCad SVG of the Phase 2/5 schematics; embed in the UI.
3. Hand-map clickable regions on the PCB photo.
4. Build the scenario JSON schema:
   ```json
   {
     "id": "scenario-rolling-picture-cap",
     "title": "Rolling picture, intermittent",
     "difficulty": 3,
     "backstory": "Customer reports the screen rolls when the cabinet warms up.",
     "faults": [
       {"target": "FB_V_LO_QC", "mode": 2, "delay_s": 30}
     ],
     "diagnosis_tree": [...],
     "score": {"max_time_s": 180, "max_points": 100}
   }
   ```
5. Implement the training-mode runner: pick a random scenario, apply
   faults via the existing cabinet bus, score the user's diagnosis.
6. Hint/reveal system after timeout or surrender.
## Deliverables to land in the same commit as the phase
- Cabinet/schematic/PCB-photo/probe UI views.
- Scenario library at `tests/scenarios/`.
- Training-mode runner under `tools/training/`.
- Initial 20-30 hand-authored scenarios.
- Updated wiki: this file, Home, Roadmap.
## What "v1 done" means
With Phase 7 complete, the project has hit the v1 deliverable from the
master plan: one full cabinet (Centipede) playable end-to-end with
fault injection on every major subsystem, training mode with
realism-weighted scenarios, and four UI views (cabinet/schematic/PCB-
photo/probe). Anything past that is improving fidelity and adding
training content.
## Future work after v1
- Tier 1 cabinets (Asteroids, Tempest, Battlezone, Missile Command,
  Black Widow). Each is months not years once Centipede is solid.
- Tier 4 (Area 51 / CoJag) as the marquee stretch goal — proves the
  framework handles a different era.
## Navigation
← Previous: [Phase 6 — CRT + trackball + audio](Phase-6-CRT-Trackball-Audio.md) ·
Next: (project plan tier expansion — see [Roadmap](../Roadmap.md))
