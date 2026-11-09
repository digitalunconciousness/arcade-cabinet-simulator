# Sources for the test-ROM effect tests

| id | Fact | Where |
|---|---|---|
| `testrom-centtest` | What the test program does and where it keeps its state: loop counter `$10-$11`, IRQ counter `$12-$13`, last random number `$14`, trackball position `$16`, boot state `$18` (`$BA` = bad ROM), random-number histogram `$20-$23`, the cell rewritten on every pass at `$0590`, the bad-ROM tile `$2A`, IRQ handler kicks the watchdog | `testrom/centtest.s` (original code, CC0) |
| `mame-centiped-map` | The centiped driver's memory map, ROM file names and IRQ/watchdog behaviour the program is written against | MAME `mame0287`, `src/mame/atari/centiped.cpp` and `centiped_v.cpp` (palette write format) |
