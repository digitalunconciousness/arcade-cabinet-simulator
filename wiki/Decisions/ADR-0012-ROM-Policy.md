# ADR-0012: ROMs, romset and what CI runs against

**Status:** accepted, with one open point (below)
**Date:** 2026-11-09
**Deciders:** project owner

## Context

Effect tests have to run the real game to prove a fault changes it, but game ROMs are copyrighted and can never be in
this repo or in a release. CI on GitHub's runners has nobody to supply a ROM.

## Decision

- **Target romset: `centiped`** (Centipede revision 4, MAME's parent set). PLAN v0.3 names this driver, and the rev 4
  source in `historicalsource/centipede` is what the POKEY golden symptom was checked against.
- **ROMs are user-supplied.** In the app, a settings screen points at a ROM folder and MAME's own verification checks
  it (PLAN v0.3). For development, ROMs sit in the git-ignored `roms/` folder. Copies uploaded to a cloud session live
  only in that session's container. ROMs are never committed, pushed, bundled or put in CI.
- **CI runs effect tests against an original test ROM**: a small 6502 program written for this project, assembled
  from source at test time and loaded under the centiped driver's ROM file names, so every fault primitive runs on
  windows-latest and ubuntu-latest. Real-game effect tests run wherever a user's ROM exists, and their evidence (hashes,
  images, JSON) is committed. Built in Stage 1.

## Open point

The ROM set supplied for Stage 0 is revision 3 (`136001-307`..`310`, MAME's `centiped3`) under the file name
`centiped.zip`; `mame -verifyroms` passes `centiped3` and fails `centiped`. The Stage 0 audit therefore ran on
`centiped3`, which is also the set the legacy app targeted. Before Stage 1's golden tests, either a rev 4 set is
supplied or this ADR is amended to rev 3 (the rev 3 source is in the same repository). A dump of the cabinet's own
EPROMs settles which revision it runs.
