# Original test ROM for the centiped driver

A small 6502 program written for this project (CC0), so CI can run every fault primitive on MAME's `centiped` driver
without a game ROM (ADR-0016). It is not Atari code and contains no Atari data.

- `centtest.s`: the program. The header says what each part is there to let a fault break.
- `asm6502.py`: a two-pass 6502 assembler in pure Python, so building needs nothing installed.
- `build_testrom.py <out>`: assembles the program, makes its XOR zero, generates tile graphics, and writes
  `<out>/centiped/` under the `centiped` set's file names. MAME prints "WRONG CHECKSUMS" and runs it.
- `test_testrom.py`: assembler encodings and the build.

The effect tests in `tests/effect/testrom/` mark themselves `testrom: true`; the runner builds the ROM into a scratch
folder by itself. The built files are never committed.
