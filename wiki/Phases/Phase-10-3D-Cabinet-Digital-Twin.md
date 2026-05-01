# Phase 10 — 3D cabinet digital twin
**Status:** ⏳ planned
**Goal:** Replace the flat prototype navigation model with an explorable 3D Centipede cabinet that shows the monitor, control panel, boards, harnesses, PSU, and audio path in their real physical positions.
**Estimate:** 10-16 weekends.

## User-facing outcome
The user can open the cabinet, move to the board cage, click the actual board or monitor section they want to inspect, inject a fault, and watch the effect propagate back into gameplay, audio, and visual output.

## Scope
- Cabinet shell and internal frame geometry.
- Board placement, monitor placement, speaker, PSU, coin door, control panel.
- Camera/navigation system for moving between exterior, control panel, monitor, and PCB views.
- Interaction hotspots that resolve to board-package entities or cabinet peripherals.
- Visual state overlays for currently faulted parts and active probe/repair targets.

## Asset pipeline
- Source dimensions from Atari documentation, cabinet measurements, and photo references.
- Produce a low/medium/high detail asset plan so the app can run on modest desktop hardware.
- Keep board interaction keyed to the canonical board package rather than hard-coded mesh IDs.

## Definition of done
1. A user can navigate from full cabinet view to specific internal components.
2. Board hotspots map to the same `ref.pin` and peripheral identifiers used by the Phase 8/9 runtime.
3. Fault injection and repair are possible from within the 3D scene.
4. The 3D view coexists with simpler 2D fallback surfaces for low-end machines or debugging.

## Non-goals for this phase
- Photorealistic rendering above all else.
- Simulating every screw, bracket, or cable tie.
- VR support.

## Navigation
← Previous: [Phase 9 — Desktop productization](Phase-9-Desktop-Productization.md) ·
Next: [Phase 11 — Interactive technician workflow](Phase-11-Interactive-Technician-Workflow.md) →