# Sources for the Centipede effect tests

Every hardware or game fact the tests in this folder rely on, keyed by the ids their `sources:` lists use. Nothing
here is copied from a manual, schematic or ROM; the entries point to where each fact can be checked.

- **MAME** is the `mame0287` tag (`patches/MAME_VERSION`), file `src/mame/atari/centiped.cpp`.
- **Original source** is `github.com/historicalsource/centipede` (rev 3 in `revision.v3/`, rev 4 in `revision.v4/`),
  read on 2026-11-09. Line numbers are approximate, after stripping CR line endings.
- **Measured** means found by a run, with the run named.

| id | Fact | Where |
|---|---|---|
| `mame-centiped-map` | CPU memory map: RAM 0x0000–0x03FF, playfield (video) RAM 0x0400–0x07BF with a write handler that marks tiles dirty, motion-object RAM 0x07C0–0x07FF, POKEY 0x1000–0x100F, IRQ acknowledge 0x1800, watchdog 0x2000 (write), program ROM 0x2000–0x3FFF | MAME `centiped_base_map` and `centiped_map` |
| `mame-centiped3-rom-map` | `centiped3` program ROMs: 307.d1 at 0x2000, 308.e1 at 0x2800, 309.fh1 at 0x3000, 310.j1 at 0x3800, 0x800 bytes each, in region `maincpu` | MAME `ROM_START( centiped3 )` |
| `mame-centiped-irq` | The IRQ is raised from the 32V level sampled on 16V edges (`generate_interrupt`, a 16-scanline timer) | MAME `centiped_state::generate_interrupt` |
| `mame-centiped-watchdog` | Watchdog of 8 vblanks | MAME `WATCHDOG_TIMER(...).set_vblank_count("screen", 8)` |
| `mame-centiped-inputs` | Ports `:IN1` (Coin 1, 1 Player Start, P1 Button 1; active low) and `:TRACK0_X` (Trackball X, analog 0–255) | Measured: listed from `manager.machine.ioport.ports` |
| `cendef-memory-map` | "VIDEO RAM:400-7BF", "PLYFLD =400 ;30 WIDE BY 32 HIGH (400-7BF)", "ZERO PAGE RAM:0-1FF" | `revision.v3/CENDEF.MAC`, header and symbol list (~l.25, ~l.61) |
| `cendef-irq` | "IRQ 4 PER FRAME (1 IN VBLANK)" | `revision.v3/CENDEF.MAC` header (~l.31) |
| `cendef-rngen` | `RNGEN =100A` (POKEY random number generator), `SKCTL =100F` | `revision.v3/CENDEF.MAC` (~l.97–98) |
| `cendef-motion-objects` | `HPOS =07D0`, `VPOS =07E0` (motion-object positions); the shooter is object 14 (0x07DE), measured by comparing runs with and without trackball motion | `revision.v3/CENDEF.MAC` (~l.63–64); measured |
| `centi3-mushroom-placement` | A mushroom's playfield address is `(RNGEN & 0xE0) \| column` for the low byte and `(RNGEN & 3) \| 4` for the high byte, so bit 1 of the second read picks offset 0x200 and up | `revision.v3/CENTI3.MAC` (~l.1219–1226) |
| `centi4-mushroom-placement` | The same code in rev 4 | `revision.v4/CENTI4.MAC` (~l.1222) |
| `centi3-pokey-hang` | "WILL HANG IF POKEY IS GONE AND D0-D7=0'S OR 1'S" (the flea set-up loop reads RNGEN until it gets a usable value) | `revision.v3/CENTI3.MAC` (~l.137) |
| `cenir3-messages` | Messages are stored as two screen-address words and ASCII text with the high bit set on the last character; "1 COIN 1 PLAY" is drawn from 0x0513 | `revision.v3/CENIR3.MAC` (`MESS` table, `ASCIN` macro); the rev 3 ROM address 0x3547 was measured by searching the ROM image |

## Not verified

- **The open-bus value** of Centipede's data bus (the value a read returns when no chip drives the bus). The `cs_dead`
  and `rom_dead` tests run with both 0x00 and 0xFF until someone reads the data-bus pull-ups off the DP-182 schematic.
- **Which chips back which ranges.** The tests act on address ranges from the memory map, not on named parts. Pin maps
  per part (lowering) are Stage 3.
- **Whether the stuck-32V bands run across or along the player's view.** Compare with a photo of the real fault.
