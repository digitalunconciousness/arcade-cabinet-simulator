# Status

What is real, what is mocked and what is unproven, as of the end of Stage 0 (2026-11-09). Nothing here counts as
done without the evidence it links to. The plan is `docs/PLAN_v3.md`; per-fault detail is `docs/FAULT_AUDIT.md`.

## Real (with evidence)

| What | Evidence |
|---|---|
| MAME 0.287 builds from the pinned tag with `patches/0001`–`0003` (the series didn't apply to the tag until Stage 0) | `patches/MAME_VERSION`, ADR-0010; `mame -version` in `evidence/stage0/results.json` |
| Headless, deterministic runs of Centipede (`centiped3`): two baseline runs match on every frame hash and every RAM byte | `evidence/stage0/results.json` (`determinism`), `evidence/stage0/baseline_hashes.txt` |
| The plugin commands a build from this repo has: `ping`, `get_state`, `pause`, `resume`, `soft_reset`, `poke_ram`, `stuck_byte`, `clear_stuck`. Pausing, injecting and resuming on an exact frame works | audit run logs in `evidence/stage0/runs/` |
| `stuck_byte` writes reach the game's RAM. Where the game doesn't rewrite the cell, they show on screen | `FAULT_AUDIT.md`, PSU and raw rows |
| `FAULT_BUFFER` and `BAD_RAM_CELL` change their own waveforms in standalone nltool runs | `evidence/stage0/runs/netlist_standalone.json`, `evidence/stage0/runs/netlist.json` |
| The legacy unit tests (117) and the audit's own tests pass | `python -m pytest -q tools tests` |

## Mocked (state or visuals that don't come from the emulated hardware)

- **Peripheral models** (PSU, CRT chassis, trackball, audio chain, coin mech, buttons, marquee, harness) are Python
  objects in `tools/peripherals/`. Their faults change Python state for the UI. Only one path leads into the game:
  a 5 V rail below 4.7 V arms a stuck byte at `0x0700`, which is a playfield cell, so it shows as one stray tile.
- **CRT faults** were drawn as a browser canvas effect and, in an uncommitted plugin, as a Lua overlay. The committed
  plugin has no `set_crt_fault`. Either way they'd be Tier C (drawn on top), not a change to the game.
- **Audio faults** change a WebAudio test tone in the browser, not MAME's sound.
- **Netlists** (`tests/netlist/centiped/*.cpp`) are labelled in their own headers as representative, not transcribed
  from the schematic. They run only in standalone nltool.

## Unproven or not working

- **Legacy faults:** 7 of 142 change the running game, and none produces the symptom it describes. 70 send only
  commands the plugin rejects, 63 send nothing, 2 are accepted and change nothing. Every fault: `docs/FAULT_AUDIT.md`.
- **Input over the protocol doesn't exist** in a build from this repo: `press_button`, `release_button`,
  `trackball_delta` and the DIP commands are rejected as unknown. Trackball faults sit on that path, so none of them
  reaches the game.
- **The board package can't load.** `boards/centipede/fault_map.json` has a `scenarios` key the loader rejects, and
  no launcher sets `CABINET_BOARD_PATH` anyway. The Board Inspector gets no schematic, and faults on the two
  address-counter pins return HTTP 404.
- **Schematic sync faults** reach MAME only as `set_crt_fault`, which the plugin rejects.
- **Training scenarios:** 3 of 12 change the game, each through a stuck byte; none shows the symptom it describes.
  `multi-fault` comes closest (a stuck tile, without the rolling band, dimming or hum).
- **Stuck bytes lose to the game** on cells it redraws every frame: the legacy plugin rewrites them after the frame is
  drawn, so the "sprite RAM glitch" and the stuck-pixel demo show on 1 of 600 frames.
- **Rev 4 (`centiped`)**, the romset ADR-0012 targets, hasn't been run: no rev 4 set has been supplied.
- **Windows:** nothing has run on Windows yet. CI is Stage 1.

## Not built yet (PLAN v0.3)

The interface-level fault engine, effect tests and CI (Stage 1), the Godot shell (Stage 2), cabinet packs (Stage 3),
the 3D cabinet (Stage 4), the training loop (Stage 5) and a second game (Stage 6).
