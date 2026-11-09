# Fault audit (Stage 0)

Every fault the legacy app offers was run headless against the live game, and its effect compared with a baseline run.
This page says which faults change the running game, how, and where the evidence is. A fault "changes the game" here
only if the screen, the game's own RAM or its resets differ from the baseline. PLAN v0.3 then asks a second question,
whether the change matches the symptom the fault describes; the summary answers that by mechanism.

**How it was run.** MAME 0.287 built from the pinned tag with `patches/0001`–`0003`, plugin `cabinet_bus` as committed,
romset `centiped3`, headless and unthrottled. Each run boots into attract mode, pauses on frame 600, applies one fault
through the legacy Flask server exactly as the app does, sends the same input every run gets (trackball motion, fire,
coin), waits one PSU-watcher tick, resumes, and runs to frame 1200. The baseline did the same without a fault and ran
twice: the two matched on every frame and every RAM byte, so any difference below comes from the fault. Harness:
`tools/audit/` (README there). Evidence: `evidence/stage0/`.

**Limits.** Attract mode only, because no input reaches the game in this build (see finding 1). Sound was off; no
legacy fault sends anything to MAME's sound. The uncommitted plugin on the maintainer's machine couldn't be audited.
The romset is rev 3, not the rev 4 that ADR-0012 targets.

**Since Stage 1** the faults that reach the game come from the new fault engine (`plugin/cabsim/`), not from anything
audited here. Each has an effect test with evidence in `evidence/stage1/`; the list is in `docs/STATUS.md`. This page
stays as the record of what the legacy app did.

## Summary by mechanism

142 legacy faults ran against the game: 7 changed its output, 70 sent only commands the plugin rejects, 63 sent
nothing to MAME, 2 were accepted and had no effect. None produced the symptom it describes. The 24 netlist-path faults
change a standalone waveform only.

| Mechanism | Faults | What reached MAME | Changes the game? | Matches its symptom? | Tier in the game |
|---|---|---|---|---|---|
| Peripheral state only: audio (4), buttons (15), coin (4), marquee (5), harness (20), PSU `dried_filter_cap` (1) | 49 | nothing | no | no | none |
| CRT chassis faults (9) and PSU `failed_regulator` (1), via `set_crt_fault` | 10 | `set_crt_fault`, rejected | no | no | would be C (overlay) |
| Trackball faults, via `trackball_delta` | 6 | `trackball_delta`, rejected | no | no | none |
| PSU rail below 4.7 V (`bad_rectifier`, `sagging_mains`, `overload_trip`) | 3 | `set_crt_fault` (rejected) and `stuck_byte 0x0700 = 0xFF` | yes: one stray tile on the bottom row (599 of 600 frames), and the game reacts to it (16 B of its RAM) | no: no dim picture, no sluggish controls | A (a RAM write), wrong symptom |
| Schematic sync-generator pins (8 pins × 3 modes × 2 server configs) | 48 | `set_crt_fault`, rejected | no | no | would be C |
| Schematic address-counter pins (2 pins × 3 modes × 2 configs) | 12 | nothing (HTTP 404) | no | no | none |
| Scenarios | 12 | see the scenario table | 3 of 12: `dim-psu-5v` and `multi-fault` add one stray tile each; `sprite-ram-glitch` shows on 1 of 600 frames | no; `multi-fault` partly (a stuck tile, but no rolling band, dimming or hum) | A where a stuck byte lands, otherwise none |
| Raw `stuck_byte` (the stuck-pixel demo) | 1 | `stuck_byte`, accepted | 1 of 600 frames | no: the tile doesn't stay | A, but the game rewrites the cell first |
| Raw `poke_ram` | 1 | `poke_ram`, accepted | no: the game rewrites the cell before the next frame | n/a | none |

Tiers follow PLAN v0.3: A acts on an emulated bus or device so the game's code produces the effect, B is a hand-made
behavioural effect, C is drawn on top. A Python state change that never reaches MAME has no tier in the game.

## Findings that change what the plan assumed

1. **No input reaches the game over the protocol.** The committed plugin (`patches/0002`) has 8 commands: `ping`,
   `get_state`, `pause`, `resume`, `soft_reset`, `poke_ram`, `stuck_byte`, `clear_stuck`. `press_button`,
   `release_button`, `trackball_delta`, `set_crt_fault`, `list_buttons` and the DIP commands are in no commit, so
   every build made from this repo, the nightly release included, answers them `unknown command`.
2. **The patch series didn't apply to MAME 0.287.** Fixed in Stage 0 (ADR-0010).
3. **The board package can't load.** `boards/centipede/fault_map.json` has a `scenarios` key that the loader in
   `tools/schematic/board_package.py` rejects (`TypeError`), and no launcher sets `CABINET_BOARD_PATH` anyway. The
   server silently falls back to the sync-generator manifest. The legacy unit tests pass only because they build their
   own board package.
4. **The netlists are representative, not transcribed.** `tests/netlist/centiped/address_decoder.cpp` says so in its
   header and refers to the sync generator the same way. They work in standalone nltool and nowhere else. PLAN v0.3
   gives netlists the job of supplying the net map for the board inspector; these can't do that until they're traced
   from the schematic.
5. **`stuck_byte` loses to the game on cells the game redraws.** The plugin rewrites the cell once per frame, after the
   frame is drawn. In attract mode the game writes `0x0540`, `0x0560`, `0x0580` and `0x0590` once every frame (counted
   with a write tap: 600 writes in 600 frames), so the screen shows the game's value: 1 of 600 frames differ. Stage 1's
   `ram_cell_stuck` has to act on the memory access itself (a tap), not after the frame.
6. **`0x0700` is playfield RAM, not scratch RAM.** The PSU watcher arms `0xFF` there when the 5 V rail drops below 4.7 V,
   calling it a "transient RAM error". It shows as one stray tile on the bottom row, and the game reacts to it (16 bytes
   of its RAM differ by frame 1200), but there is no dimming or sluggish trackball.
7. **Scenario 06's "ROM bank missing" writes go to the watchdog.** Centipede maps writes to `0x2000` to the watchdog
   reset (MAME's `centiped_base_map`; `WTCHDG =2000` in the original `CENDEF.MAC`). The ROM itself can't be written from
   the CPU bus, so the stuck bytes at `0x2000`, `0x2001` and `0x2010` change nothing.
8. **Headless runs are deterministic.** Two baseline runs matched exactly over 1201 frames, which is what Stage 1's
   effect tests need.

## Per-fault results

<!-- BEGIN GENERATED: tools/audit/report.py -->

Run: 0.287 (mame0287-3-g37f7a540), romset `centiped3`, fault applied at frame 600, compared to frame 1200. Baseline determinism: 1201 frames, 0 differing between two baseline runs, RAM identical: True.

| verdict | count |
|---|---|
| `rejected-by-plugin` | 70 |
| `not-sent` | 63 |
| `standalone-only` | 24 |
| `changes-game-output` | 7 |
| `no-change` | 2 |

### Peripheral faults (tools/peripherals, applied with POST /api/peripherals/fault)

| fault | verdict | what reached MAME | effect after injection | evidence |
|---|---|---|---|---|
| `peripheral/PSU1/bad_rectifier` | `changes-game-output` | `set_crt_fault` ×2 rejected, `stuck_byte` accepted | screen 599/600 frames, game RAM 16 B, injected cells 1 B | [run](../evidence/stage0/runs/peripheral__PSU1__bad_rectifier.json), [before](../evidence/stage0/images/baseline_f660.png) / [after](../evidence/stage0/images/peripheral__PSU1__bad_rectifier_f660.png) / [zoom](../evidence/stage0/images/peripheral__PSU1__bad_rectifier_f660_zoom.png) |
| `peripheral/PSU1/dried_filter_cap` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__PSU1__dried_filter_cap.json) |
| `peripheral/PSU1/failed_regulator` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__PSU1__failed_regulator.json) |
| `peripheral/PSU1/sagging_mains` | `changes-game-output` | `set_crt_fault` ×2 rejected, `stuck_byte` accepted | screen 599/600 frames, game RAM 16 B, injected cells 1 B | [run](../evidence/stage0/runs/peripheral__PSU1__sagging_mains.json), [before](../evidence/stage0/images/baseline_f660.png) / [after](../evidence/stage0/images/peripheral__PSU1__sagging_mains_f660.png) / [zoom](../evidence/stage0/images/peripheral__PSU1__sagging_mains_f660_zoom.png) |
| `peripheral/PSU1/overload_trip` | `changes-game-output` | `set_crt_fault` ×2 rejected, `stuck_byte` accepted | screen 599/600 frames, game RAM 16 B, injected cells 1 B | [run](../evidence/stage0/runs/peripheral__PSU1__overload_trip.json), [before](../evidence/stage0/images/baseline_f660.png) / [after](../evidence/stage0/images/peripheral__PSU1__overload_trip_f660.png) / [zoom](../evidence/stage0/images/peripheral__PSU1__overload_trip_f660_zoom.png) |
| `peripheral/COIN1/stuck_switch` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__COIN1__stuck_switch.json) |
| `peripheral/COIN1/dirty_contact` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__COIN1__dirty_contact.json) |
| `peripheral/COIN1/jammed_mech` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__COIN1__jammed_mech.json) |
| `peripheral/COIN1/miscalibrated` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__COIN1__miscalibrated.json) |
| `peripheral/MARQ1/dead_tube` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__MARQ1__dead_tube.json) |
| `peripheral/MARQ1/ballast_slow_start` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__MARQ1__ballast_slow_start.json) |
| `peripheral/MARQ1/ballast_flicker` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__MARQ1__ballast_flicker.json) |
| `peripheral/MARQ1/ballast_hum` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__MARQ1__ballast_hum.json) |
| `peripheral/MARQ1/aging_tube` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__MARQ1__aging_tube.json) |
| `peripheral/CRT1/no_hv` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__CRT1__no_hv.json) |
| `peripheral/CRT1/vertical_collapse` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__CRT1__vertical_collapse.json) |
| `peripheral/CRT1/horizontal_collapse` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__CRT1__horizontal_collapse.json) |
| `peripheral/CRT1/weak_focus` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__CRT1__weak_focus.json) |
| `peripheral/CRT1/brightness_drift` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__CRT1__brightness_drift.json) |
| `peripheral/CRT1/bad_deflection_caps` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__CRT1__bad_deflection_caps.json) |
| `peripheral/CRT1/dim_picture` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__CRT1__dim_picture.json) |
| `peripheral/CRT1/sync_lock_failure` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__CRT1__sync_lock_failure.json) |
| `peripheral/CRT1/ringing_ghosting` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__CRT1__ringing_ghosting.json) |
| `peripheral/TRACK1/dead_opto_x` | `rejected-by-plugin` | `trackball_delta` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__TRACK1__dead_opto_x.json) |
| `peripheral/TRACK1/dead_opto_y` | `rejected-by-plugin` | `trackball_delta` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__TRACK1__dead_opto_y.json) |
| `peripheral/TRACK1/dirty_roller` | `rejected-by-plugin` | `trackball_delta` ×3 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__TRACK1__dirty_roller.json) |
| `peripheral/TRACK1/seized_bearing` | `rejected-by-plugin` | `trackball_delta` ×3 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__TRACK1__seized_bearing.json) |
| `peripheral/TRACK1/failed_quadrature_phase` | `rejected-by-plugin` | `trackball_delta` ×3 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__TRACK1__failed_quadrature_phase.json) |
| `peripheral/TRACK1/encoder_cap_failure` | `rejected-by-plugin` | `trackball_delta` ×3 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__TRACK1__encoder_cap_failure.json) |
| `peripheral/AUDIO1/dead_amp` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__AUDIO1__dead_amp.json) |
| `peripheral/AUDIO1/hum` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__AUDIO1__hum.json) |
| `peripheral/AUDIO1/distortion` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__AUDIO1__distortion.json) |
| `peripheral/AUDIO1/blown_speaker` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__AUDIO1__blown_speaker.json) |
| `peripheral/BTN_START1/stuck_closed` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_START1__stuck_closed.json) |
| `peripheral/BTN_START1/stuck_open` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_START1__stuck_open.json) |
| `peripheral/BTN_START1/intermittent` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_START1__intermittent.json) |
| `peripheral/BTN_START1/bouncy` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_START1__bouncy.json) |
| `peripheral/BTN_START1/slow_release` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_START1__slow_release.json) |
| `peripheral/BTN_START2/stuck_closed` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_START2__stuck_closed.json) |
| `peripheral/BTN_START2/stuck_open` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_START2__stuck_open.json) |
| `peripheral/BTN_START2/intermittent` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_START2__intermittent.json) |
| `peripheral/BTN_START2/bouncy` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_START2__bouncy.json) |
| `peripheral/BTN_START2/slow_release` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_START2__slow_release.json) |
| `peripheral/BTN_FIRE/stuck_closed` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_FIRE__stuck_closed.json) |
| `peripheral/BTN_FIRE/stuck_open` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_FIRE__stuck_open.json) |
| `peripheral/BTN_FIRE/intermittent` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_FIRE__intermittent.json) |
| `peripheral/BTN_FIRE/bouncy` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_FIRE__bouncy.json) |
| `peripheral/BTN_FIRE/slow_release` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__BTN_FIRE__slow_release.json) |
| `peripheral/HARN_PSU_PCB/open` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_PCB__open.json) |
| `peripheral/HARN_PSU_PCB/short_to_gnd` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_PCB__short_to_gnd.json) |
| `peripheral/HARN_PSU_PCB/short_to_5v` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_PCB__short_to_5v.json) |
| `peripheral/HARN_PSU_PCB/high_resistance` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_PCB__high_resistance.json) |
| `peripheral/HARN_PSU_PCB/chafed` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_PCB__chafed.json) |
| `peripheral/HARN_PSU_MONITOR/open` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_MONITOR__open.json) |
| `peripheral/HARN_PSU_MONITOR/short_to_gnd` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_MONITOR__short_to_gnd.json) |
| `peripheral/HARN_PSU_MONITOR/short_to_5v` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_MONITOR__short_to_5v.json) |
| `peripheral/HARN_PSU_MONITOR/high_resistance` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_MONITOR__high_resistance.json) |
| `peripheral/HARN_PSU_MONITOR/chafed` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_MONITOR__chafed.json) |
| `peripheral/HARN_PSU_MARQUEE/open` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_MARQUEE__open.json) |
| `peripheral/HARN_PSU_MARQUEE/short_to_gnd` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_MARQUEE__short_to_gnd.json) |
| `peripheral/HARN_PSU_MARQUEE/short_to_5v` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_MARQUEE__short_to_5v.json) |
| `peripheral/HARN_PSU_MARQUEE/high_resistance` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_MARQUEE__high_resistance.json) |
| `peripheral/HARN_PSU_MARQUEE/chafed` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PSU_MARQUEE__chafed.json) |
| `peripheral/HARN_PCB_PANEL/open` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PCB_PANEL__open.json) |
| `peripheral/HARN_PCB_PANEL/short_to_gnd` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PCB_PANEL__short_to_gnd.json) |
| `peripheral/HARN_PCB_PANEL/short_to_5v` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PCB_PANEL__short_to_5v.json) |
| `peripheral/HARN_PCB_PANEL/high_resistance` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PCB_PANEL__high_resistance.json) |
| `peripheral/HARN_PCB_PANEL/chafed` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/peripheral__HARN_PCB_PANEL__chafed.json) |

### Schematic pin faults (boards/centipede/fault_map.json, POST /api/schematic/fault/apply)

| fault | verdict | what reached MAME | effect after injection | evidence |
|---|---|---|---|---|
| `schematic/shipped/CLK.Q/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__CLK_Q__stuck_hi.json) |
| `schematic/shipped/CLK.Q/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__CLK_Q__stuck_lo.json) |
| `schematic/shipped/CLK.Q/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__CLK_Q__open.json) |
| `schematic/shipped/H_LO.RC/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_LO_RC__stuck_hi.json) |
| `schematic/shipped/H_LO.RC/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_LO_RC__stuck_lo.json) |
| `schematic/shipped/H_LO.RC/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_LO_RC__open.json) |
| `schematic/shipped/H_HI.RC/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_HI_RC__stuck_hi.json) |
| `schematic/shipped/H_HI.RC/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_HI_RC__stuck_lo.json) |
| `schematic/shipped/H_HI.RC/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_HI_RC__open.json) |
| `schematic/shipped/H_HI.QD/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_HI_QD__stuck_hi.json) |
| `schematic/shipped/H_HI.QD/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_HI_QD__stuck_lo.json) |
| `schematic/shipped/H_HI.QD/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_HI_QD__open.json) |
| `schematic/shipped/H_HI.QC/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_HI_QC__stuck_hi.json) |
| `schematic/shipped/H_HI.QC/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_HI_QC__stuck_lo.json) |
| `schematic/shipped/H_HI.QC/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_HI_QC__open.json) |
| `schematic/shipped/H_HI.QB/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_HI_QB__stuck_hi.json) |
| `schematic/shipped/H_HI.QB/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_HI_QB__stuck_lo.json) |
| `schematic/shipped/H_HI.QB/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__H_HI_QB__open.json) |
| `schematic/shipped/V_LO.QD/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__V_LO_QD__stuck_hi.json) |
| `schematic/shipped/V_LO.QD/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__V_LO_QD__stuck_lo.json) |
| `schematic/shipped/V_LO.QD/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__V_LO_QD__open.json) |
| `schematic/shipped/V_LO.QC/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__V_LO_QC__stuck_hi.json) |
| `schematic/shipped/V_LO.QC/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__V_LO_QC__stuck_lo.json) |
| `schematic/shipped/V_LO.QC/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__V_LO_QC__open.json) |
| `schematic/shipped/ADDR_CTR.QA/stuck_hi` | `not-sent` | nothing (HTTP 404: no instrumented fault target for ADDR_CTR.QA) | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__ADDR_CTR_QA__stuck_hi.json) |
| `schematic/shipped/ADDR_CTR.QA/stuck_lo` | `not-sent` | nothing (HTTP 404: no instrumented fault target for ADDR_CTR.QA) | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__ADDR_CTR_QA__stuck_lo.json) |
| `schematic/shipped/ADDR_CTR.QA/open` | `not-sent` | nothing (HTTP 404: no instrumented fault target for ADDR_CTR.QA) | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__ADDR_CTR_QA__open.json) |
| `schematic/shipped/ADDR_CTR.QB/stuck_hi` | `not-sent` | nothing (HTTP 404: no instrumented fault target for ADDR_CTR.QB) | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__ADDR_CTR_QB__stuck_hi.json) |
| `schematic/shipped/ADDR_CTR.QB/stuck_lo` | `not-sent` | nothing (HTTP 404: no instrumented fault target for ADDR_CTR.QB) | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__ADDR_CTR_QB__stuck_lo.json) |
| `schematic/shipped/ADDR_CTR.QB/open` | `not-sent` | nothing (HTTP 404: no instrumented fault target for ADDR_CTR.QB) | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__shipped__ADDR_CTR_QB__open.json) |
| `schematic/board_package/CLK.Q/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__CLK_Q__stuck_hi.json) |
| `schematic/board_package/CLK.Q/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__CLK_Q__stuck_lo.json) |
| `schematic/board_package/CLK.Q/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__CLK_Q__open.json) |
| `schematic/board_package/H_LO.RC/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_LO_RC__stuck_hi.json) |
| `schematic/board_package/H_LO.RC/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_LO_RC__stuck_lo.json) |
| `schematic/board_package/H_LO.RC/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_LO_RC__open.json) |
| `schematic/board_package/H_HI.RC/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_HI_RC__stuck_hi.json) |
| `schematic/board_package/H_HI.RC/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_HI_RC__stuck_lo.json) |
| `schematic/board_package/H_HI.RC/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_HI_RC__open.json) |
| `schematic/board_package/H_HI.QD/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_HI_QD__stuck_hi.json) |
| `schematic/board_package/H_HI.QD/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_HI_QD__stuck_lo.json) |
| `schematic/board_package/H_HI.QD/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_HI_QD__open.json) |
| `schematic/board_package/H_HI.QC/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_HI_QC__stuck_hi.json) |
| `schematic/board_package/H_HI.QC/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_HI_QC__stuck_lo.json) |
| `schematic/board_package/H_HI.QC/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_HI_QC__open.json) |
| `schematic/board_package/H_HI.QB/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_HI_QB__stuck_hi.json) |
| `schematic/board_package/H_HI.QB/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_HI_QB__stuck_lo.json) |
| `schematic/board_package/H_HI.QB/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__H_HI_QB__open.json) |
| `schematic/board_package/V_LO.QD/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__V_LO_QD__stuck_hi.json) |
| `schematic/board_package/V_LO.QD/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__V_LO_QD__stuck_lo.json) |
| `schematic/board_package/V_LO.QD/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__V_LO_QD__open.json) |
| `schematic/board_package/V_LO.QC/stuck_hi` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__V_LO_QC__stuck_hi.json) |
| `schematic/board_package/V_LO.QC/stuck_lo` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__V_LO_QC__stuck_lo.json) |
| `schematic/board_package/V_LO.QC/open` | `rejected-by-plugin` | `set_crt_fault` rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__V_LO_QC__open.json) |
| `schematic/board_package/ADDR_CTR.QA/stuck_hi` | `not-sent` | nothing (HTTP 404: no instrumented fault target for ADDR_CTR.QA) | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__ADDR_CTR_QA__stuck_hi.json) |
| `schematic/board_package/ADDR_CTR.QA/stuck_lo` | `not-sent` | nothing (HTTP 404: no instrumented fault target for ADDR_CTR.QA) | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__ADDR_CTR_QA__stuck_lo.json) |
| `schematic/board_package/ADDR_CTR.QA/open` | `not-sent` | nothing (HTTP 404: no instrumented fault target for ADDR_CTR.QA) | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__ADDR_CTR_QA__open.json) |
| `schematic/board_package/ADDR_CTR.QB/stuck_hi` | `not-sent` | nothing (HTTP 404: no instrumented fault target for ADDR_CTR.QB) | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__ADDR_CTR_QB__stuck_hi.json) |
| `schematic/board_package/ADDR_CTR.QB/stuck_lo` | `not-sent` | nothing (HTTP 404: no instrumented fault target for ADDR_CTR.QB) | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__ADDR_CTR_QB__stuck_lo.json) |
| `schematic/board_package/ADDR_CTR.QB/open` | `not-sent` | nothing (HTTP 404: no instrumented fault target for ADDR_CTR.QB) | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/schematic__board_package__ADDR_CTR_QB__open.json) |

### Training scenarios (tests/scenarios, POST /api/scenarios/<id>/apply)

| fault | verdict | what reached MAME | effect after injection | evidence |
|---|---|---|---|---|
| `scenario/dim-psu-5v` | `changes-game-output` | `set_crt_fault` ×3 rejected, `stuck_byte` accepted, `trackball_delta` ×3 rejected | screen 599/600 frames, game RAM 16 B, injected cells 1 B | [run](../evidence/stage0/runs/scenario__dim-psu-5v.json), [before](../evidence/stage0/images/baseline_f660.png) / [after](../evidence/stage0/images/scenario__dim-psu-5v_f660.png) / [zoom](../evidence/stage0/images/scenario__dim-psu-5v_f660_zoom.png) |
| `scenario/vertical-collapse` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/scenario__vertical-collapse.json) |
| `scenario/dead-trackball-x` | `rejected-by-plugin` | `trackball_delta` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/scenario__dead-trackball-x.json) |
| `scenario/reversed-trackball` | `rejected-by-plugin` | `trackball_delta` ×3 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/scenario__reversed-trackball.json) |
| `scenario/sprite-ram-glitch` | `changes-game-output` | `stuck_byte` ×3 accepted | screen 1/600 frames, game RAM 0 B, injected cells 3 B | [run](../evidence/stage0/runs/scenario__sprite-ram-glitch.json) |
| `scenario/address-decoder-rom` | `no-change` | `stuck_byte` ×3 accepted | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/scenario__address-decoder-rom.json) |
| `scenario/hum-amp` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/scenario__hum-amp.json) |
| `scenario/dead-amp` | `not-sent` | nothing | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/scenario__dead-amp.json) |
| `scenario/sync-lock` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/scenario__sync-lock.json) |
| `scenario/ringing-ghosting` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/scenario__ringing-ghosting.json) |
| `scenario/weak-focus` | `rejected-by-plugin` | `set_crt_fault` ×2 rejected | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/scenario__weak-focus.json) |
| `scenario/multi-fault` | `changes-game-output` | `set_crt_fault` ×2 rejected, `stuck_byte` ×2 accepted | screen 599/600 frames, game RAM 16 B, injected cells 1 B | [run](../evidence/stage0/runs/scenario__multi-fault.json), [before](../evidence/stage0/images/baseline_f660.png) / [after](../evidence/stage0/images/scenario__multi-fault_f660.png) / [zoom](../evidence/stage0/images/scenario__multi-fault_f660_zoom.png) |

### Raw RAM commands (POST /api/mame/stuck_byte, /api/mame/poke_ram)

| fault | verdict | what reached MAME | effect after injection | evidence |
|---|---|---|---|---|
| `raw/stuck_byte/col16-row12-ff` | `changes-game-output` | `stuck_byte` accepted | screen 1/600 frames, game RAM 0 B, injected cells 1 B | [run](../evidence/stage0/runs/raw__stuck_byte__col16-row12-ff.json) |
| `raw/poke_ram/0x0590-ff` | `no-change` | `poke_ram` accepted | screen 0/600 frames, game RAM 0 B | [run](../evidence/stage0/runs/raw__poke_ram__0x0590-ff.json) |

### Netlist waveform path (/api/run on build/instrumented/sync_generator.cpp)

| fault | verdict | waveform changed vs normal | HSYNC/VSYNC edges (falling/rising) |
|---|---|---|---|
| `netlist/sync_generator/CLK.Q/stuck_hi` | `standalone-only` | yes | HSYNC_n: 0↓/1↑, VSYNC_n: 0↓/1↑ |
| `netlist/sync_generator/CLK.Q/stuck_lo` | `standalone-only` | yes | HSYNC_n: 0↓/1↑, VSYNC_n: 0↓/1↑ |
| `netlist/sync_generator/CLK.Q/open` | `standalone-only` | yes | HSYNC_n: 0↓/1↑, VSYNC_n: 0↓/1↑ |
| `netlist/sync_generator/H_LO.RC/stuck_hi` | `standalone-only` | yes | HSYNC_n: 756↓/757↑, VSYNC_n: 47↓/48↑ |
| `netlist/sync_generator/H_LO.RC/stuck_lo` | `standalone-only` | yes | HSYNC_n: 0↓/1↑, VSYNC_n: 0↓/1↑ |
| `netlist/sync_generator/H_LO.RC/open` | `standalone-only` | yes | HSYNC_n: 0↓/1↑, VSYNC_n: 0↓/1↑ |
| `netlist/sync_generator/H_HI.RC/stuck_hi` | `standalone-only` | yes | HSYNC_n: 47↓/48↑, VSYNC_n: 47↓/48↑ |
| `netlist/sync_generator/H_HI.RC/stuck_lo` | `standalone-only` | yes | HSYNC_n: 47↓/48↑, VSYNC_n: 0↓/1↑ |
| `netlist/sync_generator/H_HI.RC/open` | `standalone-only` | yes | HSYNC_n: 47↓/48↑, VSYNC_n: 0↓/1↑ |
| `netlist/sync_generator/H_HI.QD/stuck_hi` | `standalone-only` | yes | HSYNC_n: 94↓/95↑, VSYNC_n: 3↓/3↑ |
| `netlist/sync_generator/H_HI.QD/stuck_lo` | `standalone-only` | yes | HSYNC_n: 0↓/1↑, VSYNC_n: 3↓/3↑ |
| `netlist/sync_generator/H_HI.QD/open` | `standalone-only` | yes | HSYNC_n: 0↓/1↑, VSYNC_n: 3↓/3↑ |
| `netlist/sync_generator/H_HI.QC/stuck_hi` | `standalone-only` | yes | HSYNC_n: 94↓/95↑, VSYNC_n: 3↓/3↑ |
| `netlist/sync_generator/H_HI.QC/stuck_lo` | `standalone-only` | yes | HSYNC_n: 0↓/1↑, VSYNC_n: 3↓/3↑ |
| `netlist/sync_generator/H_HI.QC/open` | `standalone-only` | yes | HSYNC_n: 0↓/1↑, VSYNC_n: 3↓/3↑ |
| `netlist/sync_generator/H_HI.QB/stuck_hi` | `standalone-only` | no | HSYNC_n: 47↓/48↑, VSYNC_n: 3↓/3↑ |
| `netlist/sync_generator/H_HI.QB/stuck_lo` | `standalone-only` | yes | HSYNC_n: 0↓/1↑, VSYNC_n: 3↓/3↑ |
| `netlist/sync_generator/H_HI.QB/open` | `standalone-only` | yes | HSYNC_n: 0↓/1↑, VSYNC_n: 3↓/3↑ |
| `netlist/sync_generator/V_LO.QD/stuck_hi` | `standalone-only` | yes | HSYNC_n: 47↓/48↑, VSYNC_n: 6↓/6↑ |
| `netlist/sync_generator/V_LO.QD/stuck_lo` | `standalone-only` | yes | HSYNC_n: 47↓/48↑, VSYNC_n: 0↓/1↑ |
| `netlist/sync_generator/V_LO.QD/open` | `standalone-only` | yes | HSYNC_n: 47↓/48↑, VSYNC_n: 0↓/1↑ |
| `netlist/sync_generator/V_LO.QC/stuck_hi` | `standalone-only` | no | HSYNC_n: 47↓/48↑, VSYNC_n: 3↓/3↑ |
| `netlist/sync_generator/V_LO.QC/stuck_lo` | `standalone-only` | yes | HSYNC_n: 47↓/48↑, VSYNC_n: 0↓/1↑ |
| `netlist/sync_generator/V_LO.QC/open` | `standalone-only` | yes | HSYNC_n: 47↓/48↑, VSYNC_n: 0↓/1↑ |

<!-- END GENERATED -->

## Standalone netlist harnesses

`tools/audit/netlist_standalone.py` runs the nltool harnesses the wiki cites. They all run on the pinned build, and each
fault changes its own waveform. None of this reaches the game.

| Harness | Normal | Faulted |
|---|---|---|
| `fault_buffer_test.cpp`, `FB1.Y` | 4 falling / 5 rising edges | stuck-hi 0/1, stuck-lo 0/0, open 0/0 |
| `ram_region.cpp` (`BAD_RAM_CELL`), `DO` | 1 / 2 | stuck-lo 14/15; stuck-hi and flip match normal (the harness writes 1s) |
| `address_decoder.cpp`, chip selects | each ~25 / 25 | `ADDR_CTR.QB` stuck-lo: POKEY and EAROM selects 0/1, ROM and RAM selects ~50/50 |
| `sync_generator.cpp`, `VSYNC_n` | 3 / 3 | `V_LO.QC` stuck-lo: 0/1 |

Evidence: `evidence/stage0/runs/netlist_standalone.json`.
