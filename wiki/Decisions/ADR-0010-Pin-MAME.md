# ADR-0010: Pin MAME to a release tag and keep the patch series applying to it

**Status:** accepted
**Date:** 2026-11-09
**Deciders:** project owner (PLAN v0.3)

## Context

The README bootstrap cloned MAME's moving `master` and replayed `patches/*.patch` on top. The plugin reported version
0.287, but the series did not apply to the `mame0287` tag: patches `0001` and `0003` carried hunks for
`src/lib/netlist/generated/nld_devinc.h` written in a macro style (`__VA_OPT__(NET_CHECK_PARAM_COUNT(...))`) that the tag
doesn't use. `0003` depends on `0001`, so a clean checkout couldn't reproduce the netlist devices at all.

PLAN v0.3 makes effect tests the regression net for MAME's Lua API, which is not declared stable. That only works if
everyone, CI included, builds the same MAME.

## Decision

- MAME is pinned to the tag and commit in `patches/MAME_VERSION` (`mame0287`, `e776c98438a465d3486c367cbad3777a6eb7902e`).
- `git am patches/*.patch` must apply cleanly to that tag. Generated files are patched in the tag's own format.
- `0001` and `0003` were regenerated against the tag. Only their `nld_devinc.h` hunks changed (to the tag's
  `NET_REGISTER_DEVEXT` form); authorship, messages and every other line are unchanged.
- Upgrading MAME is a deliberate change: bump `MAME_VERSION`, rebase the series, rerun every effect test.

## Consequences

- CI and local builds clone the tag, not `master`, so they can be cached by tag plus a hash of the patch files.
- The nightly workflow still clones `master`. It belongs to the legacy Tauri app and isn't changed here.
