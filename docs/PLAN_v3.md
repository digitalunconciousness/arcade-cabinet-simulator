# Arcade Cabinet Simulator — Plan v0.3 + Claude Code Kickoff

Nov 9, 2026 · @Jackie

## Kickoff prompt for Claude Code

Export this document as Markdown, commit it as `docs/PLAN_v3.md`, then paste the prompt below into Claude Code at the repo root.

```text
You are continuing work on arcade-cabinet-simulator. It runs a real arcade ROM in MAME (Centipede first) and lets a user inject hardware faults and watch the game break. The goal is a native Windows and Linux desktop app with a 3D cabinet, simulated troubleshooting and repair, and a community-extensible 'cabinet pack' format so other people can add games.

Read first, in order:
1. docs/PLAN_v3.md. This is the new source of truth. Where it conflicts with arcade_cabinet_fault_simulator_plan.md or the wiki, PLAN_v3 wins.
2. wiki/Home.md and wiki/Phases/Phase-3.5-MAME-Bridge.md
3. patches/README.md, tools/preprocessor/README.md, and the cabinet_bus plugin (vendor/mame/plugins/cabinet_bus/init.lua; follow the README bootstrap if vendor/ is not cloned)

Why we are replanning:
- Most injected faults do not change the running game. Phase 3.5 says Centipede does not use MAME's netlist solver, so FAULT_BUFFER faults only affect standalone nltool netlists. Only stuck_byte and set_crt_fault touch the live game. Treat every existing fault as unproven until a test proves it.
- The desktop app is a Tauri WebView over Xvfb, MJPEG and a Flask sidecar. It only works on Linux. We are replacing it with a native Godot 4.7 app.
- Contributors must be able to add games without touching app code.

Do now: Stage 0 and Stage 1 from the Stages section of PLAN_v3. Then stop and report. Do not start Stage 2 until I say so.

Rules:
- A fault is done only when a headless test shows it changes the running game's observable output (frame hash, RAM, audio or input) and matches the expected symptom. No test, no 'complete'.
- Never mark anything complete in wiki or status docs without committed evidence (test output, before and after images). Write docs/STATUS.md listing what is real, what is mocked and what is unproven.
- Stay inside the current stage. Park new ideas in docs/BACKLOG.md.
- Windows is a first-class target. No Linux-only tools in the runtime path. CI runs on windows-latest and ubuntu-latest.
- Never commit ROMs, copyrighted manuals or schematics. Keep provenance in SOURCES.md files.
- Tag current main as legacy-tauri before changing anything. In Stage 0, list deletion candidates for me and put deletions in their own commit.
- Small commits. Run tests before each commit. Record decisions as ADRs in wiki/Decisions/.
- If a spike is blocked after about two hours of real effort, stop, write what you tried and measured, and ask me.
- For each stage, start in plan mode and show me the plan before executing.

When a stage ends, report: what changed, evidence (paths to test output and images), what is still unproven, and the proposed next step. Keep it short.
```

## Why we are replanning

Injected faults mostly do nothing to the running game because the netlists they target are not connected to it.

The repo's own Phase 3.5 notes say Centipede does not use MAME's netlist solver, so hooking a netlist into the `centiped` driver was deferred. `FAULT_BUFFER` and `BAD_RAM_CELL` faults therefore run in standalone `nltool` harnesses. The UI can show a changed waveform there while the game on screen plays on untouched.

| Fault mechanism | Reaches the live game? |
| --- | --- |
| `FAULT_BUFFER` pin faults (sync generator, address decoder) | No. Standalone `nltool` netlist only |
| `BAD_RAM_CELL` netlist device | No. Same reason |
| `stuck_byte` (Lua plugin command) | Yes. Arms a stuck RAM cell in the running machine |
| `set_crt_fault` | Visual overlay only. No effect on game logic |
| PSU, trackball, audio, coin models | Unverified. Stage 0 audits each one |

Two more problems compound this:

- **Wrapper shell.** Tauri starts a hidden Xvfb display, MAME and a PyInstaller Flask sidecar, then shows an MJPEG stream in a WebView. It only works on Linux and cannot become a real 3D app.
- **No contribution surface.** Centipede specifics live in app code and `fault_map.json`, so a new game means editing the app.

Repo hygiene also needs attention: root-level `run_*.json` and `run_status*.json` files, `GEMINI.md`, `graphify-out/`, and a README that still calls `ui/` a placeholder.

This section comes from the repo's wiki and README. Nothing was run. Stage 0 confirms or corrects it.

## Deviations from plan v0.2

Seven things change against the plan v0.2 in the repo. Everything not listed stays: Centipede first, behavioral peripheral models, no gate-level 6502 or POKEY, the training mode, and the stuck-at, open and short fault primitives.

| Area | v0.2 | v0.3 |
| --- | --- | --- |
| UI shell | Standalone web or Electron app that talks only to the bus | Native Godot 4.7 app with a 3D cabinet, Windows and Linux first |
| Game video | Not specified. Shipped as MJPEG from Xvfb | Frames from MAME go straight into a texture on the 3D monitor mesh |
| CRT fault effects | BGFX shaders inside MAME | Godot shaders on the monitor mesh |
| Primary fault path | Netlist `FAULT_BUFFER` on instrumented pins | Interface-level fault engine in the MAME plugin. Netlists become the net map and the source for fault lowering |
| Cabinet bus | JSON over TCP plus a Python or Node peripheral process | Same JSON-lines idea, versioned as Sim Control Protocol v1. No Flask sidecar |
| Platforms | Unstated, Linux in practice | Windows is a first-class target with CI |
| New | None | Cabinet Pack format so other people can add games |

Retired: Xvfb, the MJPEG stream, the Flask server, the PyInstaller sidecar and the Tauri WebView.

## Principles

A fault counts as built only when a test shows it changes the running game. Everything else follows from that.

1. **Fault-effect contract.** Every fault ships with an effect test. A headless MAME run compares baseline and faulted output (frame hash, RAM region, audio level or input stream) and asserts the expected symptom. A fault that changes nothing fails CI.
2. **Fidelity tiers, shown honestly.** Tier A: applied to an emulated bus or device, so the game's own code produces the consequences. Tier B: a hand-authored behavioral effect, such as a CRT shader. Tier C: cosmetic only. The UI labels the tier on every fault.
3. **Physical faults, lowered to primitives.** Authors describe faults the way a tech would: reference designator, pin, failure type. A lowering table maps that to one or more engine primitives. This keeps the 3D cabinet, schematic view and simulator in the same vocabulary.
4. **Game-agnostic core.** The app and engine know nothing about Centipede. All game knowledge lives in a cabinet pack.
5. **Evidence over claims.** Nothing is marked complete without committed test output or before and after images. `docs/STATUS.md` lists what is real, mocked and unproven.
6. **Windows first-class.** No Linux-only tools in the runtime path. CI on Windows and Linux.
7. **Legal hygiene.** No ROMs, no copyrighted manuals or schematics in the repo. Every fact in a pack cites a source in `SOURCES.md`.
8. **Stage discipline.** Work stays inside the current stage. New ideas go to `docs/BACKLOG.md`. A blocked spike stops and reports after about two hours.

## Architecture

The app, the MAME plugin and the pack meet only through a socket protocol and a data folder, so each can change without breaking the others.

&#91;embedded content: architecture · 3 parts, 1 data pack, 1 authoring CLI\]

The app and MAME exchange commands one way and frames, probes and state the other. Both read the same pack, and the CLI checks the pack and runs its tests against headless MAME.

**Frame transport** is decided by a measured spike in Stage 2, against a budget of 60 fps, under 8 ms added latency and under 15% CPU on Windows:

1. Frames over the socket from the plugin. Verify that the Lua API exposes screen pixels in the pinned MAME version and is fast enough.
2. A small C++ patch that publishes frames to shared memory or a named pipe.
3. libretro's MAME core loaded in-process. Whether our netlist and plugin patches survive that build is unknown.

**Audio** stays inside MAME at first. Audio faults (mute, gain, hum) are applied in the plugin. Capturing samples into Godot for spatial audio is a later spike.

**Input** is unchanged: Godot sends `press_button`, `release_button` and `trackball_delta` over the protocol.

**MAME version** is pinned. The repo's plugin reported 0.287. Upgrades are deliberate and rerun every effect test.

## Fault engine

Faults are applied at the emulated interfaces the game's own code talks to, so symptoms come out of the running game instead of being drawn on top of it.

The plugin hooks memory regions, device register reads and writes, input ports, IRQ and clock timing, and the video and sound outputs. Use MAME's memory taps or handler overrides where the pinned version allows it. Where Lua is too slow on a hot path such as main RAM, move that primitive into the C++ patch set and expose it to Lua. The budget is full game speed on a mid-range Windows laptop with a fault active.

| Primitive | Models | Example symptom | Tier |
| --- | --- | --- | --- |
| `data_bit_stuck(region, bit, level)` | Data line stuck or shorted | Garbled tiles in a RAM region | A |
| `addr_line_stuck(region, line, level)` | Address line stuck or open | Aliased writes, corrupted memory | A |
| `cs_dead(region)`, `cs_stuck(region)` | Dead or stuck chip select | Reads return open bus, writes vanish | A |
| `ram_cell_stuck(addr, bit, level)` | One failed memory cell | One bad RAM bit. Replaces `stuck_byte` | A |
| `rom_bit_flip(addr, bit)`, `rom_dead(region)` | Bad ROM bit or chip | No boot, or one routine breaks | A |
| `reg_read_override(device, reg, rule)` | A chip returning wrong register values | Failing POKEY random output | A |
| `irq_missing`, `irq_stuck`, `clock_scale(device, factor)` | Lost interrupt, slow clock | Game runs slow or freezes | A |
| `input_dead`, `input_stuck`, `input_inverted`, `input_noisy` | Switch or encoder faults | Trackball axis inverted | A |
| `sync_timing(offset, dropout)` | Sync pulse shift or loss | Sliced or rolling picture | A or B, per driver |
| `video_channel_stuck(channel, level)` | Video output line stuck | Missing color | A or B, per driver |
| `power_rail_scale(rail, factor)` | Rail sag | Resets, RAM corruption, dim CRT. Cascades into the primitives above | B |
| `audio_*` (mute, gain, hum, distortion) | Audio chain | No sound, buzz | B |
| `crt_*` (Godot shaders) | Monitor chassis | No high voltage, collapse, weak focus | B |

**Lowering.** Pack faults are written the way a tech thinks: part, pin, failure type. A lowering table resolves that to primitives, using a pin map per chip function in the pack (for example, which pins of a RAM chip are which data and address lines, and which region it backs). Illustrative example; part and pin values are placeholders:

```yaml
- id: ram-e7-pin7-stuck-low
  target: {part: E7, pin: 7}
  type: stuck_low
  lowering:
    - primitive: data_bit_stuck
      region: playfield_ram
      bit: 3
      level: 0
  tier: A
  symptom: Garbled playfield tiles, game keeps running
  sources: [service-manual, repair-log]
  effect_test: tests/ram-e7-pin7.yaml
  activation: always   # later: intermittent or thermal
```

**Effect test.** One file per fault. It runs headless, injects, compares against a baseline, then repairs and checks recovery. Illustrative example:

```yaml
id: ram-e7-pin7-stuck-low
run: {driver: centiped, frames: 600, input: attract}
inject: {fault: ram-e7-pin7-stuck-low, at_frame: 120}
assert:
  - frame_hash_differs: {from_frame: 200}
  - region_diff: {region: playfield_ram, min_changed_bytes: 1}
  - not_crashed: true
  - symptom_snapshot: golden/ram-e7-pin7.png   # saved for human review
repair:
  action: clear_fault
  assert: {frame_hash_matches_baseline: true, after_frames: 120}
```

**Golden symptoms.** Three real symptoms anchor fidelity, taken from the Lakeside Arcade Centipede repair logs and your refit: a stuck 32V sync line slices the screen horizontally, a bad ROM stops the boot, and a failing POKEY puts mushrooms on one side only. They become the first golden tests. The POKEY case probably comes down to reads of its random-number register. That is a hypothesis to verify against the `historicalsource/centipede` code before building it. Add your own photos or video of each symptom as reference.

**Netlists keep a smaller job.** They supply the net map for the board inspector, the pin maps for lowering, and standalone probe demos. Running a sub-circuit as a live netlist inside the game (the sync generator is the one candidate) is an optional later phase. Nothing depends on it.

## Cabinet packs: how other people add games

A game is a folder of data. The app and engine contain no game-specific code, so most contributions never touch C++ or Godot.

```text
packs/centipede/
  pack.toml          id, title, mame_driver, romsets, min_mame, schema_version, license, authors
  parts.yaml         cabinet graph: parts, connectors, wires, nets, each with a stable ID
  board/             netlist export + board package JSON (components, pins, nets, photo hotspots)
  model/cabinet.glb  node names equal part IDs
  faults/*.yaml      fault definitions with lowering (see Fault engine)
  scenarios/*.yaml   training scenarios: faults, backstory, diagnosis path, repairs
  tests/*.yaml       effect tests and golden snapshots
  SOURCES.md         where every fact came from
```

**One ID everywhere.** Each part, net, connector and wire has one stable ID. The same ID names it in `parts.yaml`, the glTF node, the board package and every fault target. The validator fails on any ID that is missing or dangling. This is what makes click part, inject fault, repair part work in the 3D view.

**Repairs are data too.** A fault lists what fixes it, such as `replace_part`, `reseat_connector`, `clean_contacts` or `resolder`, each naming a part. A matching repair clears the fault and the effect test checks the game recovers. A wrong repair does nothing and is logged for scoring.

**Three ways to contribute, cheapest first:**

1. Add faults and scenarios to an existing pack using primitives that already exist. YAML only.
2. Add a game pack for a MAME driver the primitives already cover. YAML, a parts graph and a `.glb` model.
3. Add a new primitive or a driver-specific hook. This needs code review and a test on every supported driver.

**Tooling** is a small `cabsim` CLI used for authoring and CI, not shipped in the player app: `cabsim pack new <driver>` scaffolds a pack, `cabsim pack validate` checks schemas, IDs and citations, and `cabsim pack test` runs the effect tests headless. JSON Schemas for every file live in the repo, with a pack CI template.

**Pull request checklist.** Validator passes. Effect tests pass. `SOURCES.md` is complete. No ROMs, manual PDFs or schematic scans are committed. 3D assets carry a license that allows redistribution. `CONTRIBUTING.md` and an Add a game guide are written during Stage 6 by actually adding a second game, ideally with someone other than the maintainer doing it.

## Native app notes

The app is a Godot project that launches like any program, spawns MAME as a child process and renders everything itself.

- **Engine.** Godot 4.7.x (4.7.1 is the current stable release at the time of writing). Pin the exact version in the repo. Use GDScript for UI and glue. Add a GDExtension in C++ or Rust only if profiling demands it.
- **Process management.** The app starts the patched MAME with the plugin enabled, passes a free localhost port, restarts MAME if it dies, and shuts it down cleanly. Whether MAME can run without a visible window and still expose frames is checked in the Stage 2 spike.
- **Monitor.** Emulated frames update an `ImageTexture` on the screen material of the monitor mesh. CRT fault shaders run on that material with uniforms per fault. The Phase 6 effect list carries over.
- **3D pipeline.** Blender to glTF 2.0 (`.glb`). One node per replaceable part, node names equal part IDs, one collision shape per node for picking. Write a short Blender export checklist in `docs/`.
- **Windows packaging.** A Godot export preset gives the app. Ship it beside a patched `mame.exe` and the plugin folder as a portable zip first, an installer later. CI builds MAME from source with MSYS2, applies `patches/*.patch` and caches the result.
- **ROMs.** The user supplies them. A settings screen points at a ROM folder, and a first-run check uses MAME's ROM verification and lists any missing set by its exact name. ROMs are never bundled or committed.
- **Other platforms.** Linux uses the same app and a patched MAME build, with an AppImage later. macOS is best effort and not in CI.
- **Migration.** Import the existing Phase 8 board package and `fault_map.json` into the pack format instead of rebuilding them. Keep the Flask and Tauri code on the `legacy-tauri` tag, not in main.

## Stages and exit criteria

Seven stages, each ending in a demo you can run and a gate that needs evidence, not a status line. Stage 1 is highlighted because it fixes the faults that did nothing.

&#91;embedded content: roadmap · 7 stages, 1 gate each\]

0. **Truth audit and cleanup.** Tag `legacy-tauri`. Inventory every fault in the UI, the scenarios and `fault_map.json`. Run each one headless against the live game and record whether output changed. Write `docs/FAULT_AUDIT.md` (fault, mechanism, tier, evidence path) and `docs/STATUS.md`. List cleanup candidates (root `run_*.json` and `run_status*.json`, `GEMINI.md`, `graphify-out/`, the stale README note), then delete them in a separate commit. Add a `CLAUDE.md` carrying the kickoff rules.
1. **Fault engine on Centipede.** Build the plugin's primitive layer and the headless effect-test runner, with CI on Windows and Linux. First faults, at least ten: `ram_cell_stuck`, `data_bit_stuck` and `addr_line_stuck` on playfield RAM, `cs_dead` on POKEY and on RAM, `rom_bit_flip`, `rom_dead`, `irq_missing`, `clock_scale`, a POKEY random-register override, and `input_inverted` on a trackball axis. Then a sync-timing fault for the sliced-screen symptom, with its tier labelled honestly. Evidence: committed hashes, diffs and before and after images, and every repair returning to baseline.
2. **Native shell spike.** A Godot project that spawns MAME, draws live frames on a quad, takes keyboard and trackball input, and applies a Stage 1 fault from a button. Measure the transport options on a real Windows machine and record the choice in an ADR. No Xvfb, WebView or Flask.
3. **Cabinet pack v1.** Write the JSON Schemas. Migrate the Centipede board package, fault map and scenarios into a pack. Add the pack loader to Godot and the plugin, and the `cabsim` validate and test commands. Remove every Centipede-specific constant from the app.
4. **3D cabinet slice.** A Blender cabinet with each part as its own node named by part ID. The live game on the monitor mesh. Click a chip, the trackball, the coin door or the PSU, inject a fault, see the symptom, then repair it. At least three faults complete the full loop.
5. **Training loop.** Scenario runner with multi-fault cases, simulated probe and multimeter tools fed by plugin telemetry, scoring, and hints. Reuse the Phase 7 content. The three golden symptoms are diagnosed and repaired end to end.
6. **Second game.** Pick the game with the maintainer, favoring simple TTL-era hardware on a driver the primitives already cover. Write the Add a game guide by doing the work. The gate is that someone other than the maintainer can follow it.

**Not scheduled yet:** wire-level harness faults, a PSU rail model, a live netlist sync generator, audio capture into Godot, intermittent and thermal activation, and parity checks against a real cabinet.

## Risks and open questions

The biggest technical risk is speed and API stability inside MAME, and Stage 1 and Stage 2 are built to expose it early.

| Risk | Mitigation |
| --- | --- |
| Lua memory taps too slow on hot RAM paths | Benchmark first in Stage 1. Move slow primitives into the C++ patch set |
| MAME's Lua API is not declared stable | Pin the MAME version. Effect tests act as the regression net on every upgrade |
| Frame transport misses the 60 fps and 8 ms budget on Windows | Three candidate transports, measured in Stage 2 before any UI work depends on one |
| Some drivers model video or timing functionally, so a Tier A fault is impossible | Label the fault Tier B or C and say so in the UI. Never present a cosmetic effect as causal |
| Agent drift back into breadth without proof | Gates need committed evidence. You review each stage report before the next stage starts |

**Open questions for you:**

- [ ] Licenses for app code, pack data and 3D assets. MAME patches follow MAME's own terms
- [ ] How to handle schematics and manuals: link to the Internet Archive sources and commit only derived netlists, or something stricter
- [ ] Which second game for Stage 6
- [ ] A Windows 10 or 11 machine for Stage 2 measurements and playtests. CI only covers headless runs
- [ ] Photos or video of the three golden symptoms from your real Centipede, as reference captures
- [ ] Keep one monorepo for now and split packs into their own repos once a second contributor appears?

## Sources

Checked on 2026-11-09. The repo pages were read as published. Nothing in the repo was run.

- [Repository and README](https://github.com/digitalunconciousness/arcade-cabinet-simulator)
- [Wiki home, phase status](https://github.com/digitalunconciousness/arcade-cabinet-simulator/blob/main/wiki/Home.md)
- [Phase 3.5, MAME bridge and the netlist limitation](https://github.com/digitalunconciousness/arcade-cabinet-simulator/blob/main/wiki/Phases/Phase-3.5-MAME-Bridge.md)
- [Plan v0.2](https://github.com/digitalunconciousness/arcade-cabinet-simulator/blob/main/arcade_cabinet_fault_simulator_plan.md)
- [Godot 4.7.1 release](https://github.com/godotengine/godot/releases/tag/4.7.1-stable)
- [MAME Lua scripting documentation](https://docs.mamedev.org/luascript/index.html)
- [libretro MAME core](https://github.com/libretro/mame)
