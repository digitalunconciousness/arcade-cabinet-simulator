# ADR-0016: An original test ROM for CI

**Status:** accepted
**Date:** 2026-11-09
**Deciders:** project owner (the CI answer recorded in ADR-0012)

## Context

CI on GitHub's runners can't use a game ROM (ADR-0012), but PLAN v0.3 wants a fault that changes nothing to fail CI.
MAME runs the centiped driver with ROM files whose checksums don't match: it warns and carries on.

## Decision

- `testrom/centtest.s` is a small 6502 program written for this project (CC0). `testrom/asm6502.py` is a pure-Python
  assembler, so the build needs nothing installed on Windows or Linux. `build_testrom.py` writes the program, generated
  tile graphics and an empty PROM under the `centiped` set's file names into a scratch folder. No built file is
  committed.
- The program gives every primitive something observable to break: a boot XOR check with a bad-ROM screen, an IRQ
  handler that kicks the watchdog, a free-running loop counter, a POKEY random-number histogram, a cell rewritten on
  every pass, and a motion object that follows the trackball.
- `tests/effect/testrom/` has a twin of each real-game test. CI runs them on ubuntu-latest and windows-latest.

## Consequences

- CI proves each primitive changes what a program on the real driver sees. It doesn't prove the game's symptom; the
  real-game tests do that, and their committed evidence is the record.
- Changing the program changes its baselines, not its tests: each test compares its own two runs.
