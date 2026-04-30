# MAME patch series
Each `*.patch` here is a `git format-patch` export of a commit we keep on
top of upstream MAME, kept under VCS so the tree at `vendor/mame/` can be
re-cloned at will without losing our work.
## Apply to a fresh clone
```bash
cd vendor/mame
git am /home/jackie/arcade-sim/patches/*.patch
```
That replays every patch in numbered order and leaves the tree on a real
commit, ready to be rebased onto a newer upstream MAME tag later.
## Regenerate after editing the MAME tree
After committing further changes inside `vendor/mame/`, refresh this dir:
```bash
cd vendor/mame
git format-patch -o /home/jackie/arcade-sim/patches/ \\
    --start-number=1 mame0.287..HEAD
```
(or substitute whatever upstream tag/sha we are based on for `mame0.287`).
## Current series
- `0001-Add-FAULT_BUFFER-netlist-device-for-runtime-fault-in.patch`
  - Adds `FAULT_BUFFER` netlist device with stuck-hi / stuck-lo / open modes.
  - Registers it in the build (`netlist.lua`) and the two checked-in
    generated files (`nld_devinc.h`, `lib_entries.hxx`).
