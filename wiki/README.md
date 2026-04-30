# Project wiki
This directory is the canonical wiki for the Arcade Cabinet Fault Simulator
project. It is tracked in the same git repo as the code so wiki updates can
ride along with the commits that justify them.
## Convention
1. Every completed phase MUST update this wiki in the same commit (or PR)
   that lands the phase deliverables. The relevant pages are:
   - `Phases/Phase-N-<name>.md` — append a "Status: complete" header and
     fill in the deliverables, gotchas, verification commands, and links
     to relevant code/docs.
   - `Home.md` — bump the "current phase" pointer and the deliverables list.
   - `Roadmap.md` — tick off the phase, surface the next-phase entry.
2. Significant cross-cutting decisions (architectural calls, scope cuts,
   technology choices) get an ADR in `Decisions/ADR-NNNN-<slug>.md`.
3. New netlist devices we add to MAME get a page under `Devices/` mirroring
   `docs/devices/<device>.md`. Keep them in sync.
4. If the prose explains *what the system is* or *how to use it*, prefer
   the wiki. If it explains *how a single device works internally*, prefer
   `docs/devices/`. Cross-link freely.
## Layout
```
wiki/
├── README.md              ← you are here
├── Home.md                ← landing page; current phase pointer
├── Roadmap.md             ← phase plan summary
├── Build-Notes.md         ← deps, build commands, audio config, runbook
├── Glossary.md            ← terminology cheat-sheet
├── Phases/                ← one page per phase (0..N)
├── Devices/               ← one page per netlist device we add
└── Decisions/             ← ADRs (Architectural Decision Records)
```
## Publishing to GitHub Wiki (optional)
GitHub gives every repo a separate wiki repo at
`https://github.com/<owner>/<repo>.wiki.git` with built-in rendering and a
sidebar TOC. Run `tools/sync-wiki.sh` to mirror this directory to that
wiki repo. Workflow:
```bash
# 1. Make sure the GitHub wiki is enabled and has at least one page
#    (a one-time setup — the wiki repo doesn't exist until the first page
#    is created via the GitHub web UI). Run:
#       gh repo edit --enable-wiki
#    then visit the repo's Wiki tab and click "Create the first page".
# 2. Sync this directory.
./tools/sync-wiki.sh
```
The sync script is one-way (this directory → GitHub Wiki). Don't edit pages
directly in the GitHub Wiki UI; they'll be overwritten on next sync.
