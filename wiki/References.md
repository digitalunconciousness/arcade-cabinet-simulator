# References
Source materials we use as factual reference for circuit topology,
timing, and fault categories. We don't redistribute these PDFs in this
repo; `docs/{centipede,wells-gardner,cojag}/` and `scans/centipede/` are
gitignored. The project relies on each contributor having sourced their
own legal copy.
## Centipede
- **Atari TM-182** — *Centipede Operation, Maintenance and Service Manual
  with Illustrated Parts Catalog*. Multiple printings (1st through 6th).
  Mirrored at the Museum of the Game (`arcade-museum.com`) and other
  arcade-preservation archives.
- **Atari DP-182** — *Centipede Drawing Package Supplement*. The
  schematics. Eight sheets across four PDFs (`-01A`, `-01B`, `-02A`,
  `-02B`). Mirrored at `arcarc.xmission.com/PDF_Arcade_Atari_Kee/Centipede/`.
- **Atari TM-188 / DP-188** — Centipede Cocktail variants (we don't
  target this cabinet for v1, but useful for cross-reference).
- **Atari TM-189 / DP-189** — Centipede Cabaret variants.
- **Atari TM-192** — Centipede Signature Analysis Guide. Useful for the
  Phase 5 RAM region work.
- **MAME driver source** — `vendor/mame/src/mame/atari/centiped.cpp`.
  Authoritative for memory map, screen timing, and chip clocks. We
  cross-check our netlist against it.
- **Sean Riddle's PCB scans** (`seanriddle.com`) — high-resolution photos
  of the physical board. Source of truth for the PCB-photo UI view and
  for picking physically-adjacent pin pairs for `FAULT_SHORT`.
## Monitor (Wells-Gardner 19K6100)
- Wells-Gardner 19K6100 service literature. Source of fault-category
  list for the CRT chassis model.
## Atari CoJag / Area 51 (Tier 4 stretch goal)
- Atari CoJag service docs.
- Raymond Jett's CoJag troubleshooting guide (PLD Archive wiki).
## How we use these
1. **Factual circuit topology** — chip locations, pin connections, net
   names — is reference material for the netlist transcription. We cite
   the document number in source comments, e.g. `// per DP-182 sheet 4`.
2. **Fault-category lists** (PSU, monitor, trackball, etc.) inform the
   peripheral models in Phase 4 and 6.
3. **Self-test / signature-analysis sequences** (TM-192) inform the
   training-mode scenario library in Phase 7.
4. We do NOT bulk-paste manual content into the repo or wiki. When a
   netlist sub-circuit is transcribed from a schematic, the source
   citation is a one-line comment, not a copy of the page.
## Local layout (gitignored)
After running the bootstrap from `README.md`, plus your own document
sourcing:
```
docs/centipede/
    Centipede_TM-182_*_printing.pdf      ← service manual
    Centipede_DP-182-1st-0[12][AB]*.pdf  ← schematics, 4 PDFs
docs/wells-gardner/
    Wells-Gardner_19K6100_*.pdf          ← chassis service manual
docs/cojag/
    Atari_CoJag_*.pdf
    Raymond_Jett_CoJag_troubleshooting_guide.pdf
scans/centipede/
    sean-riddle/*.{jpg,png}              ← PCB scans
    our-board/*.{jpg,png}                ← scans of the board we just refit
```
