# arcade-cabinet-simulator: rules for Claude sessions

The source of truth is `docs/PLAN_v3.md`. Where it conflicts with `arcade_cabinet_fault_simulator_plan.md` or the wiki,
PLAN_v3 wins. What is real, mocked and unproven today is in `docs/STATUS.md`. Ideas outside the current stage go to
`docs/BACKLOG.md`.

## Rules (from the PLAN v0.3 kickoff)

- A fault is done only when a headless test shows it changes the running game's observable output (frame hash, RAM,
  audio or input) and matches the expected symptom. No test, no "complete".
- Never mark anything complete in the wiki or status docs without committed evidence (test output, before and after
  images).
- Stay inside the current stage. Park new ideas in `docs/BACKLOG.md`.
- Windows is a first-class target. No Linux-only tools in the runtime path. CI runs on windows-latest and ubuntu-latest.
- Never commit ROMs, copyrighted manuals or schematics. Keep provenance in `SOURCES.md` files.
- Small commits. Run the tests before each commit. Record decisions as ADRs in `wiki/Decisions/`.
- If a spike is still blocked after about two hours of real effort, stop, write down what was tried and measured, and ask.
- Each stage starts in plan mode, and the maintainer approves the plan before anything is executed. Don't start the next
  stage until told to.
- At the end of a stage, report what changed, the evidence (paths to test output and images), what is still unproven, and
  the proposed next step. Keep it short.

## Repo facts

- **MAME is pinned** at the tag in `patches/MAME_VERSION` (mame0287). `vendor/mame/` is a git-ignored clone of that tag,
  and `git am patches/*.patch` must apply to it cleanly. Upgrading is a deliberate change that reruns every effect test.
- Build inside `vendor/mame/`: `make SOURCES=src/mame/atari/centiped.cpp TOOLS=1 USE_QTDEBUG=0`. This builds `mame` and
  `nltool`.
- **Romset:** ADR-0012 targets `centiped` (rev 4); the set on hand is `centiped3` (rev 3), which Stage 1 tests use
  (ADR-0012 amendment). Every effect test names its romset.
- **ROMs** are user-supplied and live in the git-ignored `roms/` folder. Never commit, push or bundle them. CI runs effect
  tests against the original test ROM in `testrom/` (ADR-0016), never a game ROM.
- **The fault engine** is the `cabsim` Lua plugin in `plugin/cabsim/` (ADR-0013), loaded with
  `-pluginspath "<mame>/plugins;<repo>/plugin" -plugin cabsim`. The app talks to it over Sim Control Protocol v1
  (`docs/protocol/scp-v1.md`). C++ goes into `patches/` only where Lua can't reach (ADR-0014).
- **Effect tests**: one YAML file per fault in `tests/effect/<game|testrom>/`, run with
  `python -m tools.cabsim effect run <files or folders> --mame vendor/mame/mame --rompath roms`
  (format and assertions: `tools/cabsim/README.md`; repair semantics: ADR-0015). Real-game evidence goes in
  `evidence/stage1/`. Every fact a test relies on is cited in that folder's `SOURCES.md`.
- **CI**: `.github/workflows/effect-tests.yml` (ubuntu-latest, windows-latest).
- The legacy Tauri + Xvfb + MJPEG + Flask app stays on `main` until the Stage 2 Godot spike works. The snapshot from before
  v0.3 is the `legacy-tauri` tag.
- The cabinet_bus plugin that a fresh checkout reproduces is the one in `patches/0002`. Commands that the server or wiki
  mention but that patch lacks don't exist in any build made from this repo.
- Unit tests: `python -m pytest -q tools tests testrom` (needs `pytest`, `pyyaml`, `pillow`; the legacy tests also need
  `flask`, `requests`, `jsonschema`, `pyparsing`, `lark`).
- The Stage 0 truth audit is in `tools/audit/` (how to run it: `tools/audit/README.md`). It drives the legacy server from a
  `legacy-tauri` worktree and records evidence in `evidence/stage0/`.
- `digitalunconciousness/Gatbox` is a separate public project, read-only from here. Its roster, manuals, ROM dumps and rail
  logs never come into this repo. Ideas for using its data are in `docs/BACKLOG.md`.
