# ADR-0014: A small C++ patch for the faults Lua can't reach

**Status:** accepted
**Date:** 2026-11-09
**Deciders:** project owner (PLAN v0.3, Stage 1)

## Context

PLAN v0.3 puts the fault engine in a Lua plugin, and moves a primitive into C++ only where Lua can't do the job or is too
slow. MAME 0.287's Lua API covers memory (read and write taps, ROM regions, shares) and inputs, but has no way to:

- hold a CPU's interrupt line clear or asserted (needed for `irq_missing` and `irq_stuck`);
- change a device's clock (needed for `clock_scale`). `device_t::set_clock_scale()` exists in C++ and drives MAME's own
  overclock sliders, but it isn't bound to Lua.

## Decision

`patches/0004` adds, generically and for any driver:

- `device_execute_interface::set_input_line_override(line, state)`. While the override is set, `set_state_synced`
  substitutes it for whatever state the driver asks for, and it remembers the driver's last request. Releasing the override
  re-applies that request, so the line goes straight back to what the driver wants.
- Lua bindings: `device:set_input_line_override(line, "clear" | "assert" | "none" | nil)`,
  `device:input_line_override(line)`, and a read/write `device.clock_scale`. Both reject bad input with a Lua error instead
  of aborting MAME.

The patch touches `diexec.h`, so applying it rebuilds most of the emulator core once.

## Consequences

- Upgrading MAME means rebasing four patches instead of three. The override code is small and lives where input lines are
  delivered, so it should rebase cleanly while that design holds.
- Every other primitive stays in Lua (ADR-0013). If the Stage 1 benchmark shows Lua taps too slow on a hot path, that
  primitive moves into this patch set.
