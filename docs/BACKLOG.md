# Backlog

Ideas that came up outside the current stage. Each names the stage it would fit. Nothing here is scheduled until a stage
plan picks it up.

## From Gatbox (digitalunconciousness/Gatbox)

Gatbox is the bench box that dumps EPROMs, logs supply rails in cabinets and keeps a library of games, manuals and rail
limits. Its data lives on the Pi and the archive server, not in its public repo. Nothing from its roster, manuals or dumps
is copied here.

- **Stage 3: pack metadata from the library.** The library-v1 read side (`docs/contract/library-v1/read/` in Gatbox) has
  `rom_list` (ROM names, sizes and hashes from `mame -listxml`; no ROM data), `rail_limit` and `fact` records that each
  cite `doc_id`, page and quote, and `document` records for manuals. These map onto `pack.toml` romsets, PSU rail limits
  and `SOURCES.md` citations. A `cabsim` importer could read a reader-token feed or an exported JSON, vendoring the read
  contract byte-identical the way cabcrawl and the Tech Tracker do. Needs an ADR on coupling to Gatbox's contract.
- **Stage 3: ROM check.** Gatbox dumps are read twice and checked with `mame -romident`, so a dump that passed there can be
  pointed at directly from the app's ROM folder setting. The archive never gives ROM images to readers, so this stays a
  local file path, not an API call.
- **Stage 5+: real rail behaviour.** Rail CSVs from cabinets left overnight (sags, glitches, power cycles found by
  `gatbox-rail-report`) could drive `power_rail_scale` profiles and intermittent activation. Fits the unscheduled
  "PSU rail model" and "parity checks against a real cabinet" items in PLAN_v3.
- **Stage 5: scenario seeds.** Repair orders on the hub, with their traces, are real backstories and diagnosis paths for
  training scenarios.
- **Stage 6: second game.** Prefer a game that already has a dump and a manual in the library.

## Found during Stage 0

- **The newer cabinet_bus plugin.** The wiki and server use `press_button`, `trackball_delta`, `set_crt_fault` and DIP
  commands that no commit contains. If that `init.lua` still exists on the maintainer's machine, it's worth a look before
  Stage 2 for the input and DIP code. It is not needed for the audit, which tests what the repo reproduces.
- **Stage 3: the board package doesn't load.** `boards/centipede/fault_map.json` carries a `scenarios` key that
  `tools/schematic/board_package.py` rejects. Fix it as part of migrating the board package into the Centipede pack,
  with a test that loads the real file, not a fixture.
- **Stage 3/4: trace the netlists from the schematic.** The sync generator and address decoder netlists say they are
  representative, not transcribed. PLAN v0.3 wants netlists as the net map and pin maps for lowering, which needs the
  real board.
