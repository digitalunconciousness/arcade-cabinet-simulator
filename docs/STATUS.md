# Status

What is real, what is mocked and what is unproven, as of the end of Stage 1 (2026-11-09). Nothing here counts as done
without the evidence it links to. The plan is `docs/PLAN_v3.md`.

## Real (with evidence)

### Fault engine (Stage 1)

Each fault below has an effect test that runs `centiped3` headless twice from power-on. One run has the fault. The test
asserts the symptom while the fault is active, and that every frame after the repair (a power cycle, ADR-0015) matches
the baseline. All 16 pass. A second full run gave identical hashes. Each also has a twin on the original test ROM
(`tests/effect/testrom/`, all 12 pass), which is what CI runs.

| Primitive | Fault | Tier | Symptom shown | Evidence |
|---|---|---|---|---|
| `data_bit_stuck` | Playfield RAM D3 stuck low | A | garbled tiles and text across the playfield; the game keeps running | [result](../evidence/stage1/centipede/centipede__playfield-ram-data-bit3-stuck-low/result.json) |
| `ram_cell_stuck` | Cell 0x0590 bit 3 stuck high | A | one wrong character that holds against the game's every-frame write (498/499 frames) | [result](../evidence/stage1/centipede/centipede__playfield-ram-cell-0590-bit3-stuck-high/result.json) |
| `addr_line_stuck` | Playfield RAM A5 stuck high | A | rows alias in pairs (480 of 480 pairs identical; baseline 105 differ) | [result](../evidence/stage1/centipede/centipede__playfield-ram-address-a5-stuck-high/result.json) |
| `cs_dead` (RAM) | Playfield RAM chip select dead, open bus 0x00 / 0xFF | A | every playfield byte reads open bus, writes lost | [00](../evidence/stage1/centipede/centipede__playfield-ram-chip-select-dead-open-bus-00/result.json), [ff](../evidence/stage1/centipede/centipede__playfield-ram-chip-select-dead-open-bus-ff/result.json) |
| `cs_dead` (device) | POKEY chip select dead from power-on, 0x00 | A | black screen, watchdog resets (137 in 1070 frames), as the source warns | [result](../evidence/stage1/centipede/centipede__pokey-chip-select-dead-open-bus-00/result.json) |
| `cs_dead` (device) | POKEY chip select dead from power-on, 0xFF | A | game runs with no mushrooms (placed past the playfield) | [result](../evidence/stage1/centipede/centipede__pokey-chip-select-dead-open-bus-ff/result.json) |
| `reg_read_override` | POKEY RNGEN bit 1 stuck low. **Golden: mushrooms on one side** | A | 37 mushrooms on one side, 0 on the other (baseline 22/15) | [result](../evidence/stage1/centipede/centipede__pokey-random-bit1-stuck-low/result.json) |
| `rom_dead` | ROM J1 (reset vector) dead, 0x00 / 0xFF. **Golden: bad ROM stops the boot** | A | never boots: black, frozen | [00](../evidence/stage1/centipede/centipede__rom-j1-dead-open-bus-00/result.json), [ff](../evidence/stage1/centipede/centipede__rom-j1-dead-open-bus-ff/result.json) |
| `rom_bit_flip` | ROM FH1, one bit of the coin message | A | "1 GOIN 1 PLAY" | [result](../evidence/stage1/centipede/centipede__rom-fh1-bit-flip-coin-message/result.json) |
| `irq_missing` | Main CPU IRQ never arrives | A | freezes; watchdog resets every 8 frames | [result](../evidence/stage1/centipede/centipede__maincpu-irq-missing/result.json) |
| `clock_scale` | Main CPU at a quarter of its clock | A | runs slow: 263 repeated frames of 498 (baseline 44); at half speed the game still keeps up | [result](../evidence/stage1/centipede/centipede__maincpu-clock-quarter-speed/result.json) |
| `input_inverted` | Trackball X inverted | A | shooter moves −44 where the baseline moves +44 | [result](../evidence/stage1/centipede/centipede__trackball-x-inverted/result.json) |
| `sync_timing` | 32V stuck high, picture only. **Golden: sliced screen** | B | picture cut into repeated 32-line bands; the game untouched (a plain clear matches the baseline) | [result](../evidence/stage1/centipede/centipede__sync-32v-stuck-high-video/result.json) |
| `sync_timing` + `irq_missing` | 32V stuck low, picture and IRQ | B+A | bands, then frozen with watchdog resets | [result](../evidence/stage1/centipede/centipede__sync-32v-stuck-low-with-irq/result.json) |

Before/after/zoom images sit next to each `result.json`. Per-test notes and sources: the YAML files in
`tests/effect/centipede/` and `tests/effect/centipede/SOURCES.md`.

### Infrastructure

| What | Evidence |
|---|---|
| MAME 0.287 builds from the pinned tag with `patches/0001`–`0004`, and the series applies cleanly to a fresh tag | `patches/MAME_VERSION`, ADR-0010, ADR-0014 |
| The fault engine plugin (`plugin/cabsim/`): game-agnostic primitives, frame-exact timeline mode, Sim Control Protocol v1 | ADR-0013, `docs/protocol/scp-v1.md`, `tools/cabsim/scp_smoke.py` (10/10 checks) |
| Lua tap cost: taps on the hottest RAM run at ~0.74 of no-fault speed, still ~18x real time on a 2.1 GHz Xeon vCPU | `evidence/stage1/benchmark.json` |
| The effect-test runner (`tools/cabsim/`) and its unit tests | `python -m pytest -q tools/cabsim` |
| The original test ROM and its assembler (`testrom/`) | `python -m pytest -q testrom`; `evidence/stage1/testrom/` |
| The Stage 0 truth audit of the legacy app | `docs/FAULT_AUDIT.md`, `evidence/stage0/` |

## Mocked (from the legacy app, unchanged)

- **Peripheral models** (PSU, CRT chassis, trackball, audio chain, coin mech, buttons, marquee, harness) are Python
  state in `tools/peripherals/`. Only a 5 V rail below 4.7 V reaches the game, as one stray tile.
- **CRT faults** are a browser canvas effect; the committed legacy plugin has no `set_crt_fault`.
- **Audio faults** change a WebAudio test tone, not MAME's sound.
- **Netlists** (`tests/netlist/centiped/*.cpp`) are representative, not transcribed from the schematic; standalone only.

## Unproven

- **CI hasn't run yet.** GitHub Actions gives this repository no runner (an account lock; every job since at least
  2026-08-10 ended in about 3 seconds with no logs). CI moves to the owner's Forgejo (ADR-0017,
  `docs/ci-forgejo.md`): `.forgejo/workflows/effect-tests.yml` and the GitHub-to-Forgejo sync script are ready. The
  shared build script built MAME from scratch in a fresh checkout (pinned tag, all four patches, 8 min 51 s on 4 cores,
  1.8 GB of build tree), and that binary passed the 12 test-ROM effect tests and the protocol smoke test. The sync
  script was tested against local stand-in repositories. No Forgejo run has happened yet. On Linux, every CI step was replayed in a clean checkout and
  venv: 22 unit tests, 12/12 test-ROM effect tests, 16 real-game tests skipped (no ROMs), protocol smoke 10/10.
- **Windows**: nothing has run on Windows. The MSYS2 build follows MAME's own CI recipe but is untested, and on Forgejo
  it needs a Windows machine registered as a runner.
- **Primitives without an effect test yet**: `irq_stuck`, `input_dead`, `input_stuck`, `input_noisy`. They exist in
  `plugin/cabsim/primitives.lua` and are not counted as built.
- **Known gaps** in built primitives:
  - `cs_dead` on a device can't cancel a write, so a strobe register write (POKEY's STIMER, SKRES, POTGO) still acts.
  - 32V stuck high would also fire the IRQ on every 16-line edge, which no primitive models.
- **Hardware facts not verified**: the open-bus value of Centipede's data bus, which chips back which ranges, and
  which way the stuck-32V bands run on the real monitor. See `tests/effect/centipede/SOURCES.md`.
- **Rev 4 (`centiped`)**: no rev 4 set has been supplied; Stage 1 ran on rev 3 (ADR-0012 amendment).
- **Full speed on a mid-range Windows laptop with a fault active** (PLAN v0.3's budget): measured only on this Linux vCPU.

## Not built yet (PLAN v0.3)

The Godot shell and the frame transport (Stage 2), cabinet packs with part/pin lowering and JSON Schemas (Stage 3), the
3D cabinet (Stage 4), the training loop (Stage 5) and a second game (Stage 6).
