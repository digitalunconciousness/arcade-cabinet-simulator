# MAME patch series

Each `*.patch` here is a `git format-patch` export of a commit we keep on top of upstream MAME. The series is applied to
the tag pinned in `MAME_VERSION`, and must apply to that tag cleanly (ADR-0010).

## Apply to a fresh clone

From the repo root:

```bash
read -r MAME_TAG MAME_SHA < patches/MAME_VERSION
git clone --depth=1 --branch "$MAME_TAG" https://github.com/mamedev/mame.git vendor/mame
git -C vendor/mame rev-parse HEAD        # must print $MAME_SHA
git -C vendor/mame am "$PWD"/patches/*.patch
```

That replays every patch in numbered order and leaves the tree on real commits.

## Regenerate after editing the MAME tree

After committing further changes inside `vendor/mame/`, refresh this folder from the repo root:

```bash
read -r MAME_TAG MAME_SHA < patches/MAME_VERSION
git -C vendor/mame format-patch -o ../../patches/ --start-number=1 "$MAME_SHA"..HEAD
```

Then check the result on a clean clone of the tag (the commands above) before committing.

## Upgrading MAME

Change `MAME_VERSION`, rebase the series onto the new tag, regenerate, and rerun every effect test. A generated file such
as `src/lib/netlist/generated/nld_devinc.h` must be patched in the format that tag uses.

## Current series

- `0001-Add-FAULT_BUFFER-netlist-device-for-runtime-fault-in.patch`
  - Adds the `FAULT_BUFFER` netlist device with stuck-hi, stuck-lo and open modes.
  - Registers it in the build (`netlist.lua`) and in the two checked-in generated files (`nld_devinc.h`, `lib_entries.hxx`).
- `0002-Add-cabinet_bus-plugin-socket-bridge-for-the-cabinet.patch`
  - Adds `plugins/cabinet_bus/` (Lua plugin and `plugin.json`).
  - Listens on `127.0.0.1:5051` for JSON-line commands: `ping`, `get_state`, `pause`, `resume`, `soft_reset`, `poke_ram`,
    `stuck_byte`, `clear_stuck`. Defaults to `start: false`; load it with `-plugin cabinet_bus`.
  - These are the only commands a build from this repo has. The server and wiki also use `press_button`, `trackball_delta`,
    `set_crt_fault` and DIP commands, which no commit contains (see `docs/FAULT_AUDIT.md`).
- `0003-Add-BAD_RAM_CELL-netlist-device-for-cell-level-RAM-f.patch`
  - Adds the `BAD_RAM_CELL` netlist device (a 16 × 1 SRAM with one stuck cell) and registers it like `0001`.
