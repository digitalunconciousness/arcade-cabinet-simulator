# license:CC0-1.0
"""Tests for the 6502 assembler and the test ROM build. No MAME needed."""

from __future__ import annotations

import sys
import tempfile
import unittest
from functools import reduce
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from asm6502 import AsmError, assemble  # noqa: E402
import build_testrom  # noqa: E402


def code(src: str) -> bytes:
    out, _ = assemble(".org $2000\n" + src)
    return bytes(out[a] for a in sorted(out))


class AssemblerTests(unittest.TestCase):
    def test_addressing_modes_encode_like_the_datasheet(self):
        cases = {
            "LDA #$12": "a9 12",
            "LDA $12": "a5 12",
            "LDA $12,X": "b5 12",
            "LDA $1234": "ad 34 12",
            "LDA $1234,X": "bd 34 12",
            "LDA $1234,Y": "b9 34 12",
            "LDA ($12,X)": "a1 12",
            "LDA ($12),Y": "b1 12",
            "LDX $12,Y": "b6 12",
            "STA $0100,X": "9d 00 01",
            "JMP ($1234)": "6c 34 12",
            "ASL A": "0a",
            "LSR": "4a",
            "RTI": "40",
            "INC $07D0": "ee d0 07",
        }
        for src, want in cases.items():
            self.assertEqual(code(src).hex(" "), want, src)

    def test_branches_are_relative(self):
        self.assertEqual(code("loop: DEX\n BNE loop").hex(" "), "ca d0 fd")
        self.assertEqual(code(" BEQ ahead\n NOP\nahead: NOP").hex(" "), "f0 01 ea ea")

    def test_forward_reference_stays_absolute(self):
        # a name defined later can't be proven to fit in zero page in pass 1
        self.assertEqual(code(" LDA later\nlater = $10").hex(" "), "ad 10 00")

    def test_low_high_byte_and_data(self):
        self.assertEqual(code(" LDA #<$1234\n LDX #>$1234\n .byte 1, \"AB\"\n .word $BEEF").hex(" "),
                         "a9 34 a2 12 01 41 42 ef be")

    def test_errors(self):
        with self.assertRaises(AsmError):
            code(" BNE far\n .fill 200, 0\nfar: NOP")
        with self.assertRaises(AsmError):
            code(" STY $1234,Y")
        with self.assertRaises(AsmError):
            code(" LDA missing")


class TestRomTests(unittest.TestCase):
    def test_program_checks_out(self):
        image, symbols = build_testrom.program_image()
        self.assertEqual(len(image), 0x2000)
        self.assertEqual(reduce(lambda a, b: a ^ b, image), 0, "XOR of the program must be zero")
        vectors = image[0x1FFA:]
        self.assertEqual(int.from_bytes(vectors[2:4], "little"), symbols["RESET"])
        self.assertEqual(int.from_bytes(vectors[4:6], "little"), symbols["IRQ"])
        self.assertEqual(int.from_bytes(vectors[0:2], "little"), symbols["NMI"])

    def test_build_writes_the_centiped_file_names(self):
        with tempfile.TemporaryDirectory() as td:
            out = build_testrom.build(Path(td)) / "centiped"
            names = sorted(p.name for p in out.iterdir())
            want = sorted([n for n, _ in build_testrom.PROGRAM] + build_testrom.GFX + [build_testrom.PROM])
            self.assertEqual(names, want)
            for n, _ in build_testrom.PROGRAM:
                self.assertEqual((out / n).stat().st_size, 0x800)

    def test_tile_zero_is_blank_and_others_are_not(self):
        gfx = build_testrom.tile_graphics()
        blank = 0x40 * 8
        self.assertEqual(gfx[blank:blank + 8] + gfx[0x800 + blank:0x800 + blank + 8], bytes(16))
        other = 0x41 * 8
        self.assertNotEqual(gfx[other:other + 8], bytes(8))


if __name__ == "__main__":
    unittest.main()
