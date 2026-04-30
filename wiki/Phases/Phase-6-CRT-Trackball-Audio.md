# Phase 6 — CRT monitor + trackball + audio chain
**Status:** 🚧 not started
**Goal:** The biggest remaining peripherals get behavioral models with
fault categories and (for the CRT) shader-level visual rendering.
- **CRT chassis** (Wells-Gardner 19K6100) — chassis-level model with
  named fault categories applied as shader effects on top of MAME's
  framebuffer output: no HV (dark/faint), vertical collapse, horizontal
  collapse, weak focus, brightness drift, color drift, deflection-cap
  tearing, dim picture, sync-lock failure, ringing/ghosting.
- **Trackball** (Atari 4.5″ optical) — quadrature-pulse model with
  dead-opto, dirty-roller, seized-bearing, failed-quadrature-phase,
  encoder-cap-failure faults.
- **Audio chain** (POKEY → amp → speaker) — fault categories: dead amp,
  hum, distortion, blown speaker.
**Estimate:** 8–12 weekends per the project plan. The largest single phase.
## Why this is big
- The CRT shader work is the bulk of the visual-fidelity story. Each
  named fault is its own GLSL/BGFX effect.
- The CRT model also consumes from PSU rails (Phase 4) and accepts
  video+sync from the PCB (Phase 2/5), so fault propagation across
  subsystems lights up here in earnest.
- Trackball faults are some of the most common things you actually
  see on a working Centipede in the wild — high training value.
## Plan sketch
1. Wire the CRT model's input to MAME's framebuffer output via the
   cabinet bus.
2. Implement the named fault categories as a shader pipeline.
3. Couple the CRT's input rails to the Phase 4 PSU model so a sagging
   PSU dims the picture.
4. Trackball model in Python; integrates with MAME's input system via
   the cabinet_bus plugin.
5. Audio model: post-process MAME's audio output through fault filters
   (clipping for distortion, low-pass for blown speaker, hum injection).
## Deliverables to land in the same commit as the phase
- `tools/peripherals/crt.py`, `trackball.py`, `audio.py`.
- Shader effects under `ui/shaders/`.
- Cabinet-bus extensions for input synthesis (trackball motion, button
  presses).
- UI extensions: CRT preview pane, trackball "wear" knob, audio
  controls.
- Updated wiki: this file, Home, Roadmap.
## Open questions
- How tightly does the CRT preview need to be coupled to MAME's actual
  rendering vs. a separate preview that shows the simulated chassis
  behavior on a known test pattern? Both have demo value.
- Audio fault realism is hard — most fault categories are subtle.
  Probably worth EE consultation here.
## Navigation
← Previous: [Phase 5 — Address decoder + RAM](Phase-5-Address-Decoder-RAM.md) ·
Next: [Phase 7 — Cabinet UI + training mode](Phase-7-Cabinet-UI-Training.md) →
