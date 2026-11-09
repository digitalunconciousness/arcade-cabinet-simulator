# cabsim (Stage 1: effect tests)

Runs fault effect tests headless against MAME with the `cabsim` plugin (`plugin/cabsim/`), and writes the evidence.
A fault counts as built only when its effect test passes (PLAN v0.3, principle 1).

```bash
# real game (your own ROM set in roms/; never committed)
python -m tools.cabsim effect run tests/effect/centipede/*.yaml \
    --mame vendor/mame/mame --rompath roms --out evidence/stage1/centipede
# the original test ROM (what CI runs)
python -m tools.cabsim effect run tests/effect/testrom/*.yaml \
    --mame vendor/mame/mame --rompath <folder from testrom/build_testrom.py> --out evidence/stage1/testrom
python -m tools.cabsim.bench ...      # Lua tap cost, see bench.py
python -m tools.cabsim.scp_smoke ...  # Sim Control Protocol v1 over a socket
python -m pytest -q tools/cabsim      # the runner's own tests
```

Needs Python 3.10+, PyYAML and Pillow. A test whose romset isn't in `--rompath` is skipped, not failed.

## How a test runs

Each test runs MAME twice from power-on, unthrottled, with no video window and no sound:

- **baseline**: every event in `run.events`, plus the repair's reset if it has one;
- **faulted**: the same, plus the fault at `inject.at_frame` and `clear_all` at `repair.at_frame`.

So the two runs differ only in the fault. The plugin hashes the exported frame on every frame, and saves RAM ranges and
the screen at checkpoints. `expect` compares the two runs while the fault is active; `expect_after_repair` checks that
after the repair the faulted run matches the baseline frame for frame. Frames are counted across resets.

Repair actions (ADR-0015): `clear` (the fault is removed and nothing else happens), `clear_and_soft_reset`,
`clear_and_hard_reset` (a power cycle, as a tech would after replacing a part; MAME rebuilds the machine and the faulted
run must then match the baseline exactly).

## Test file

```yaml
id: centipede/playfield-ram-data-bit3-stuck-low   # unique; also the evidence folder name
title: Playfield RAM data line D3 stuck low
romset: centiped3
display: {rotate: 90}        # degrees counter-clockwise to stand the monitor upright in saved PNGs
tier: A                      # A, B or C (PLAN v0.3); B+A when a fault has parts at both tiers
golden: ...                  # optional: the real-cabinet symptom this test anchors
symptom: ...                 # what a tech would see; the assertions must show it
note: ...                    # how the fault maps to the hardware, measurements, known gaps
sources: [mame-centiped-map] # ids in the folder's SOURCES.md
run:
  end_frame: 1500
  checkpoints: [600, 900, 1100, 1500]   # RAM ranges and the screen are saved here
  ram: [{name: playfield, space: ":maincpu", start: 0x0400, end: 0x07bf}]
  events:                    # in both runs: {frame, type, ...}
    - {frame: 2, type: reset, kind: hard}           # reset: soft | hard
    - {frame: 300, type: button, port: ":IN1", field: "Coin 1", down: true}
    - {frame: 450, type: analog, port: ":TRACK0_X", field: "Trackball X", delta: 3}
    - {frame: 0, type: watch_writes, space: ":maincpu", start: 0x1000, end: 0x100f}
    - {frame: 600, type: trace_reads, space: ":maincpu", start: 0x2000, end: 0x3fff, until: 900}
inject: {at_frame: 600, primitive: data_bit_stuck, params: {...}}
expect: [...]
repair: {at_frame: 1100, action: clear_and_hard_reset}
expect_after_repair: [...]
```

Assertions (`asserts.py`): `frame_hash_differs`, `frame_hash_matches_baseline`, `screen_frozen`, `repeated_frames`,
`region_bits`, `region_diff`, `ram_value`, `all_bytes`, `aliased_pairs`, `count_split`, `count_values`, `ram_trend`,
`frame_rows_aliased`, `not_crashed`, `resets`, `no_plugin_errors`, plus `snapshot` (saves before, after and an 8× zoom
of the changed pixels).

## Primitives

The plugin's primitives (`plugin/cabsim/primitives.lua`) take explicit device tags, address ranges, regions and ports, so
nothing in them is specific to one game:

`ram_cell_stuck`, `data_bit_stuck`, `addr_line_stuck`, `cs_dead` (`kind: ram | device`), `reg_read_override`,
`rom_bit_flip`, `rom_dead`, `irq_missing`, `irq_stuck`, `clock_scale`, `input_inverted`, `input_dead`, `input_stuck`,
`input_noisy`, `sync_timing`.

## Evidence

`<out>/<id>/result.json` holds the verdict, every check with its numbers, the frame hashes at the checkpoints for both
runs, the plugin's events and the timings. Snapshots sit next to it as `baseline_f<frame>.png`, `faulted_f<frame>.png`
and `zoom_f<frame>.png`.
