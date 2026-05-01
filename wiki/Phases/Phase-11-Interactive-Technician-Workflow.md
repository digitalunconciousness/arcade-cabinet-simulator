# Phase 11 — Interactive technician workflow
**Status:** ⏳ planned
**Goal:** Turn the simulator from a fault-picker into a real diagnosis-and-repair loop where the user inspects symptoms, probes likely causes, performs a virtual repair, and gets immediate feedback on whether the repair fixed the cabinet.
**Estimate:** 8-12 weekends.

## What changes here
- Faults stop being a developer-only control surface and become part of authored service exercises.
- The user can inspect, test, isolate, replace, and re-test parts.
- Training outcomes can be measured against repair quality, not only symptom recognition.

## Core features
- Symptom-first scenarios: the cabinet presents a fault without telling the user where it lives.
- Probe actions: logic probe, scope-like net preview, monitor observations, audio observations, input tests.
- Repair actions: reseat connector, replace chip, swap monitor component, repair trace, rebuild harness, clear and re-test.
- Evaluation: whether the chosen repair matched the actual failure and whether collateral faults remain.
- Persistence: save the current cabinet state, active faults, repairs attempted, and scenario score.

## Runtime dependencies
- Board-package fault metadata from Phase 8.
- Desktop app packaging and local persistence from Phase 9.
- 3D cabinet hotspots from Phase 10, with 2D fallback when needed.

## Definition of done
1. At least one complete service workflow exists from symptom to confirmed repair.
2. The user can perform both correct and incorrect repairs and see different outcomes.
3. Scenario scoring captures time, test sequence, replacement accuracy, and successful verification.
4. The workflow is accessible from both 2D and 3D cabinet views.

## Navigation
← Previous: [Phase 10 — 3D cabinet digital twin](Phase-10-3D-Cabinet-Digital-Twin.md) ·
Next: [Phase 12 — Physical prototype + parts plan](Phase-12-Physical-Prototype-Parts-Plan.md) →