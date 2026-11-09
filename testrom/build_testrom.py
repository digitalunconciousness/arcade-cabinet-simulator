#!/usr/bin/env python3
# license:CC0-1.0
"""Build the original Centipede-driver test ROM set into a folder.

Assembles centtest.s, makes the XOR of the program ROM zero (the program's
boot check), generates tile graphics, and writes everything under the file
names of MAME's `centiped` set, so `-rompath <out> centiped` runs it. MAME
reports wrong checksums and runs it anyway. Nothing built here is
committed; tests build it into a temporary folder.

  python testrom/build_testrom.py <out>      # writes <out>/centiped/*
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from asm6502 import assemble  # noqa: E402

ROMSET = "centiped"
PROGRAM = [  # (file, CPU address) for the centiped (rev 4) set
    ("136001-407.d1", 0x2000),
    ("136001-408.e1", 0x2800),
    ("136001-409.fh1", 0x3000),
    ("136001-410.j1", 0x3800),
]
GFX = ["136001-211.f7", "136001-212.hj7"]  # the two halves of region gfx1
PROM = "136001-213.p4"
CHIP = 0x800


def program_image() -> tuple[bytes, dict[str, int]]:
    code, symbols = assemble((HERE / "centtest.s").read_text())
    image = bytearray([0xFF] * 0x2000)  # unprogrammed EPROM bytes read as $FF
    for addr, byte in code.items():
        if not 0x2000 <= addr <= 0x3FFF:
            raise ValueError(f"byte outside the program ROM at {addr:#06x}")
        image[addr - 0x2000] = byte
    fix = symbols["CKFIX"] - 0x2000
    image[fix] = 0
    x = 0
    for b in image:
        x ^= b
    image[fix] = x  # now the XOR of all 8 KB is zero
    return bytes(image), symbols


def tile_graphics() -> bytes:
    """Two 2 KB halves, one bit plane each, 8 bytes per 8x8 character. The
    playfield draws character (code & $3F) + $40; code 0 is blank and every
    other character gets a distinct pattern in both planes, so all four
    colours appear."""
    gfx = bytearray(0x1000)
    for ch in range(256):
        for row in range(8):
            if ch == 0x40:
                a = b = 0
            else:
                a = (ch * 37 + row * 11 + 0x5A) & 0xFF
                b = ((ch * 13) ^ (row * 0x29) ^ 0xC3) & 0xFF
            gfx[ch * 8 + row] = a
            gfx[0x800 + ch * 8 + row] = b
    return bytes(gfx)


def build(out: Path) -> Path:
    folder = out / ROMSET
    folder.mkdir(parents=True, exist_ok=True)
    image, _ = program_image()
    for name, addr in PROGRAM:
        off = addr - 0x2000
        (folder / name).write_bytes(image[off:off + CHIP])
    gfx = tile_graphics()
    (folder / GFX[0]).write_bytes(gfx[:CHIP])
    (folder / GFX[1]).write_bytes(gfx[CHIP:])
    (folder / PROM).write_bytes(bytes(256))
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    print(build(Path(sys.argv[1])))
