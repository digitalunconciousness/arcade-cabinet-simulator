# ADR-0015: Effect tests compare against a baseline, and repair means a power cycle

**Status:** accepted
**Date:** 2026-11-09
**Deciders:** project owner (PLAN v0.3, Stage 1)

## Context

PLAN v0.3 makes an effect test the bar for every fault: a headless run that shows the fault changes the running game,
that the change matches the symptom, and that repair brings the game back. "Changes the game" needs something to
compare against. "Back to normal" needs a definition, because clearing a RAM fault doesn't undo what the game already
did with the bad data.

## Decision

- **One YAML file per fault** (`tools/cabsim/README.md`). The runner builds two timeline plans for the `cabsim` plugin:
  a baseline and a faulted run that share every event except the fault and its clearing. Both run headless and
  unthrottled from power-on. Headless MAME is deterministic, and two full runs of the Centipede suite gave identical
  hashes.
- **Assertions name the symptom.** Each test states its symptom in words and checks it with numbers: frame hashes,
  RAM contents, resets, counters, row aliasing in the exported frame. A test may only claim what its assertions show.
  Where a fault does something other than expected, the test records what it does (for example, the dead POKEY with
  open bus 0xFF doesn't hang the board; the mushrooms go missing instead).
- **Repair is a power cycle.** `clear_and_hard_reset` removes the fault and power-cycles the board, as a tech would
  after replacing a part. The baseline power-cycles on the same frame, and every frame after that must match the
  baseline exactly. A purely visual (Tier B) fault can use `clear` with no reset, which then proves the game itself was
  never changed.
- **Evidence** per test: `result.json` (every check with its numbers, the hashes at the checkpoints for both runs, the
  plugin's events) and before/after/zoom PNGs. Real-game evidence is committed. The test ROM's runs in CI are uploaded
  as artifacts.

## Consequences

- A real-game test needs the user's ROM set and skips without it. CI covers every primitive through the test ROM
  (ADR-0016).
- The format is Stage 1's. Stage 3 moves fault definitions and their tests into the cabinet pack, with JSON Schemas and
  part/pin lowering on top.
