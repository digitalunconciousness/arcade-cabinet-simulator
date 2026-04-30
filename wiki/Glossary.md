# Glossary
Project-specific terms and arcade jargon that show up across the docs.
## Project terms
- **Cabinet bus** — the message-passing layer between the MAME-side PCB
  simulator and the peripheral models (PSU, monitor, trackball, etc.).
  Carries power rails, signals, and mechanical events.
- **FAULT_BUFFER** — netlist device we add to MAME that pass-through by
  default and can be flipped into stuck-hi / stuck-lo / open at runtime.
  The atomic unit of fault injection on the digital side.
- **FAULT_SHORT** — planned two-terminal device for pin-to-pin shorts.
  Inserted only between physically-adjacent pin pairs read from the KiCad
  PCB layout. Not yet implemented (planned for Phase 1.5).
- **Manifest** — JSON file emitted by the auto-instrumentation
  preprocessor mapping `(refdes, pin) → fault_device_name`. The UI uses it
  to resolve a click on a schematic / PCB photo to a runtime fault target.
- **Preprocessor** — the Python tool at `tools/preprocessor/instrument.py`
  that walks a MAME netlist `.cpp` and inserts a `FAULT_BUFFER` on every
  fault-eligible pin.
## MAME / netlist terms
- **netlist** — MAME's gate-level circuit simulator (`src/lib/netlist/`).
  Solves analog and logic networks together at variable timesteps.
- **NETLIB_OBJECT / NETLIB_DEVICE_IMPL** — macros for declaring a netlist
  device. The `NETLIB_DEVICE_IMPL` connection string uses `+` for
  required user-connected inputs and `@` for auto-connected power pins.
- **nltool** — standalone netlist runner shipped with MAME. Loads a
  `.cpp` netlist, runs the solver for N seconds, logs nets to disk.
  Built only when `TOOLS=1` is passed to `make`.
- **tristate_output_t** — netlist output type that supports high-Z. We
  use it on `FAULT_BUFFER.Y` so OPEN-mode behavior is real.
- **POKEY** — Atari's combined I/O + sound chip used in Centipede. We
  keep it as MAME's existing functional model (no plans to netlist).
- **CoJag** — Atari's mid-90s arcade platform built around the Atari
  Jaguar's "Tom" and "Jerry" custom chips. Area 51 runs on CoJag and is
  our marquee Tier-4 example for stretch goals.
## Arcade hardware terms
- **JAMMA** — standardized arcade wiring harness (Japan Amusement Machine
  Manufacturers Association, 1985-ish). One harness model can serve dozens
  of cabinets.
- **CRT chassis** — the analog board that drives a CRT monitor (deflection,
  HV, video amp). For Centipede this is a Wells-Gardner 19K6100.
- **Service manual** — the official paper documentation arcade ops used
  for repair. We rely on TM-179 (Centipede) as the source of truth for
  schematics and fault categories.
- **Sean Riddle** — well-known archivist of arcade PCB scans. We use his
  Centipede board photos as the basis for the PCB-photo UI view.
## Methodology terms
- **ADR** — Architectural Decision Record. A short markdown note in
  `wiki/Decisions/` capturing a non-trivial design call and its
  alternatives.
- **Phase** — a milestone-sized chunk of work from the project plan.
  Phases land as commits that update both code and the wiki.
- **Tier** (1-5) — era-based grouping of arcade titles by how easily our
  framework ports to them. See [Roadmap](Roadmap.md) for details.
