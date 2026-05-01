# Phase 12 — Physical prototype + parts plan
**Status:** ⏳ planned
**Goal:** Prepare the project to leave pure software by defining the physical cabinet build, board sourcing/refurbishment plan, replacement parts strategy, and the validation loop that compares the real cabinet against the simulator.
**Estimate:** 10-20 weekends plus parts lead time.

## Why this is the bridge to reality
- Once the software twin is good enough, the next bottleneck is no longer code. It is cabinet, PCB, monitor, controls, harness, and replacement-part availability.
- The simulator becomes much more valuable when it is calibrated against a real machine or a real board stack under controlled faults.

## Deliverables
- Cabinet BOM: woodwork, hardware, monitor, PSU, PCB stack, trackball, controls, audio chain, harness connectors.
- Board refurbishment checklist: known bad components, socketing strategy, cap kits, spare logic families, ROM handling.
- Parts sourcing matrix: original part, acceptable substitute, risk notes, lead times.
- Bench bring-up runbook: safe power-up sequence, monitor precautions, isolation transformer assumptions, expected voltages.
- Simulator parity checklist: which faults can be validated directly against real hardware and which remain approximations.

## Validation loop
1. Reproduce a simulator scenario on real hardware where safe and practical.
2. Capture video, audio, voltage, and probe observations.
3. Compare those observations against the simulator output.
4. Tune the simulator models or scenario descriptions where the real cabinet differs materially.

## Definition of done
1. A documented parts-and-sourcing plan exists for a full Centipede cabinet bring-up.
2. The project has a known-safe bench procedure for validating repairs and induced faults.
3. The simulator has a parity checklist that distinguishes validated behavior from educated approximation.
4. There is a practical path from software-only development to a working physical cabinet project.

## Navigation
← Previous: [Phase 11 — Interactive technician workflow](Phase-11-Interactive-Technician-Workflow.md) ·
Next: physical cabinet acquisition, refurbishment, and parity tuning work