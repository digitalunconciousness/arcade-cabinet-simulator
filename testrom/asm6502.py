# license:CC0-1.0
"""A small two-pass assembler for the NMOS 6502 (documented opcodes only).

Just enough for testrom/centtest.s, in pure Python so building the test ROM
needs nothing installed on Windows or Linux.

Syntax, one statement per line, ';' starts a comment:
  label:                   a label (also allowed before an instruction)
  NAME = expr              a constant
  .org expr                set the address; bytes are placed at their address
  .byte expr, ...          bytes; a "string" emits its ASCII codes
  .word expr, ...          little-endian words
  .fill count, value       count copies of a byte
  LDA #expr / LDA expr / LDA expr,X / LDA (expr),Y / LDA (expr,X) / JMP (expr) / ASL A / ASL
Expressions: numbers ($hex, %binary, decimal), names, + and -, and the
unary < (low byte) and > (high byte). A name not yet defined in pass 1
makes the operand absolute (two bytes) so sizes never change between passes.
"""

from __future__ import annotations

import re

# mnemonic -> {mode: opcode}
# modes: imp acc imm zp zpx zpy abs abx aby ind izx izy rel
OPS: dict[str, dict[str, int]] = {}


def _def(mn: str, **modes: int) -> None:
    OPS[mn] = modes


_def("ADC", imm=0x69, zp=0x65, zpx=0x75, abs=0x6D, abx=0x7D, aby=0x79, izx=0x61, izy=0x71)
_def("AND", imm=0x29, zp=0x25, zpx=0x35, abs=0x2D, abx=0x3D, aby=0x39, izx=0x21, izy=0x31)
_def("ASL", acc=0x0A, zp=0x06, zpx=0x16, abs=0x0E, abx=0x1E)
_def("BIT", zp=0x24, abs=0x2C)
for _mn, _op in (("BPL", 0x10), ("BMI", 0x30), ("BVC", 0x50), ("BVS", 0x70),
                 ("BCC", 0x90), ("BCS", 0xB0), ("BNE", 0xD0), ("BEQ", 0xF0)):
    _def(_mn, rel=_op)
_def("BRK", imp=0x00)
_def("CMP", imm=0xC9, zp=0xC5, zpx=0xD5, abs=0xCD, abx=0xDD, aby=0xD9, izx=0xC1, izy=0xD1)
_def("CPX", imm=0xE0, zp=0xE4, abs=0xEC)
_def("CPY", imm=0xC0, zp=0xC4, abs=0xCC)
_def("DEC", zp=0xC6, zpx=0xD6, abs=0xCE, abx=0xDE)
_def("EOR", imm=0x49, zp=0x45, zpx=0x55, abs=0x4D, abx=0x5D, aby=0x59, izx=0x41, izy=0x51)
for _mn, _op in (("CLC", 0x18), ("SEC", 0x38), ("CLI", 0x58), ("SEI", 0x78), ("CLV", 0xB8),
                 ("CLD", 0xD8), ("SED", 0xF8), ("TAX", 0xAA), ("TXA", 0x8A), ("DEX", 0xCA),
                 ("INX", 0xE8), ("TAY", 0xA8), ("TYA", 0x98), ("DEY", 0x88), ("INY", 0xC8),
                 ("TXS", 0x9A), ("TSX", 0xBA), ("PHA", 0x48), ("PLA", 0x68), ("PHP", 0x08),
                 ("PLP", 0x28), ("RTI", 0x40), ("RTS", 0x60), ("NOP", 0xEA)):
    _def(_mn, imp=_op)
_def("INC", zp=0xE6, zpx=0xF6, abs=0xEE, abx=0xFE)
_def("JMP", abs=0x4C, ind=0x6C)
_def("JSR", abs=0x20)
_def("LDA", imm=0xA9, zp=0xA5, zpx=0xB5, abs=0xAD, abx=0xBD, aby=0xB9, izx=0xA1, izy=0xB1)
_def("LDX", imm=0xA2, zp=0xA6, zpy=0xB6, abs=0xAE, aby=0xBE)
_def("LDY", imm=0xA0, zp=0xA4, zpx=0xB4, abs=0xAC, abx=0xBC)
_def("LSR", acc=0x4A, zp=0x46, zpx=0x56, abs=0x4E, abx=0x5E)
_def("ORA", imm=0x09, zp=0x05, zpx=0x15, abs=0x0D, abx=0x1D, aby=0x19, izx=0x01, izy=0x11)
_def("ROL", acc=0x2A, zp=0x26, zpx=0x36, abs=0x2E, abx=0x3E)
_def("ROR", acc=0x6A, zp=0x66, zpx=0x76, abs=0x6E, abx=0x7E)
_def("SBC", imm=0xE9, zp=0xE5, zpx=0xF5, abs=0xED, abx=0xFD, aby=0xF9, izx=0xE1, izy=0xF1)
_def("STA", zp=0x85, zpx=0x95, abs=0x8D, abx=0x9D, aby=0x99, izx=0x81, izy=0x91)
_def("STX", zp=0x86, zpy=0x96, abs=0x8E)
_def("STY", zp=0x84, zpx=0x94, abs=0x8C)

SIZE = {"imp": 1, "acc": 1, "imm": 2, "zp": 2, "zpx": 2, "zpy": 2, "abs": 3, "abx": 3, "aby": 3,
        "ind": 3, "izx": 2, "izy": 2, "rel": 2}
ZP_FORM = {"abs": "zp", "abx": "zpx", "aby": "zpy"}


class AsmError(Exception):
    pass


class _Undefined(Exception):
    pass


def _split_args(text: str) -> list[str]:
    out, cur, quoted = [], "", False
    for ch in text:
        if ch == '"':
            quoted = not quoted
        if ch == "," and not quoted:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


class Assembler:
    def __init__(self) -> None:
        self.symbols: dict[str, int] = {}

    # ------------------------------------------------------------ expressions
    def value(self, expr: str, strict: bool) -> int:
        expr = expr.strip()
        if not expr:
            raise AsmError("empty expression")
        if expr[0] == "<":
            return self.value(expr[1:], strict) & 0xFF
        if expr[0] == ">":
            return (self.value(expr[1:], strict) >> 8) & 0xFF
        tokens = re.findall(r"[+-]|[^+-]+", expr)
        total, sign = 0, 1
        for t in tokens:
            t = t.strip()
            if t == "+":
                sign = 1
                continue
            if t == "-":
                sign = -1
                continue
            total += sign * self._atom(t, strict)
            sign = 1
        return total

    def _atom(self, t: str, strict: bool) -> int:
        if t.startswith("$"):
            return int(t[1:], 16)
        if t.startswith("%"):
            return int(t[1:], 2)
        if t.isdigit():
            return int(t)
        if len(t) == 3 and t[0] == t[2] == "'":
            return ord(t[1])
        if re.fullmatch(r"[A-Za-z_.][A-Za-z0-9_.]*", t):
            if t in self.symbols:
                return self.symbols[t]
            if strict:
                raise AsmError(f"undefined name {t!r}")
            raise _Undefined(t)
        raise AsmError(f"bad expression {t!r}")

    # --------------------------------------------------------------- operands
    @staticmethod
    def _mode(mn: str, operand: str) -> tuple[str, str]:
        op = operand.strip()
        modes = OPS[mn]
        if not op:
            return ("acc" if "acc" in modes and "imp" not in modes else "imp"), ""
        if op.upper() == "A" and "acc" in modes:
            return "acc", ""
        if "rel" in modes:
            return "rel", op
        if op.startswith("#"):
            return "imm", op[1:]
        m = re.fullmatch(r"\((.+),\s*[Xx]\)", op)
        if m:
            return "izx", m.group(1)
        m = re.fullmatch(r"\((.+)\),\s*[Yy]", op)
        if m:
            return "izy", m.group(1)
        m = re.fullmatch(r"\((.+)\)", op)
        if m:
            return "ind", m.group(1)
        m = re.fullmatch(r"(.+),\s*[Xx]", op)
        if m:
            return "abx", m.group(1)
        m = re.fullmatch(r"(.+),\s*[Yy]", op)
        if m:
            return "aby", m.group(1)
        return "abs", op

    # ------------------------------------------------------------------ passes
    def _statements(self, source: str):
        for lineno, raw in enumerate(source.splitlines(), 1):
            line = raw.split(";", 1)[0].rstrip()
            if not line.strip():
                continue
            m = re.match(r"\s*([A-Za-z_.][A-Za-z0-9_.]*):\s*(.*)$", line)
            label = None
            if m:
                label, line = m.group(1), m.group(2)
            yield lineno, raw, label, line.strip()

    def assemble(self, source: str) -> dict[int, int]:
        """Return {address: byte}."""
        decisions: dict[int, str] = {}
        for pass_no in (1, 2):
            strict = pass_no == 2
            pc = 0
            out: dict[int, int] = {}
            for lineno, raw, label, stmt in self._statements(source):
                try:
                    if label:
                        if pass_no == 1 and label in self.symbols:
                            raise AsmError(f"label {label!r} defined twice")
                        self.symbols[label] = pc
                    if not stmt:
                        continue
                    m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", stmt)
                    if m:
                        try:
                            self.symbols[m.group(1)] = self.value(m.group(2), strict)
                        except _Undefined:
                            pass
                        continue
                    word, _, rest = stmt.partition(" ")
                    word_u = word.upper()
                    if word_u == ".ORG":
                        pc = self.value(rest, True)
                    elif word_u in (".BYTE", ".WORD"):
                        for arg in _split_args(rest):
                            if arg.startswith('"'):
                                for ch in arg.strip('"'):
                                    out[pc] = ord(ch)
                                    pc += 1
                                continue
                            try:
                                v = self.value(arg, strict)
                            except _Undefined:
                                v = 0
                            if word_u == ".BYTE":
                                out[pc] = v & 0xFF
                                pc += 1
                            else:
                                out[pc], out[pc + 1] = v & 0xFF, (v >> 8) & 0xFF
                                pc += 2
                    elif word_u == ".FILL":
                        count, val = (self.value(a, True) for a in _split_args(rest))
                        for _ in range(count):
                            out[pc] = val & 0xFF
                            pc += 1
                    elif word_u in OPS:
                        pc = self._instruction(word_u, rest, pc, out, decisions, lineno, strict)
                    else:
                        raise AsmError(f"unknown statement {word!r}")
                except (AsmError, ValueError) as e:
                    raise AsmError(f"line {lineno}: {e}\n  {raw}") from None
        return out

    def _instruction(self, mn, operand, pc, out, decisions, lineno, strict) -> int:
        mode, expr = self._mode(mn, operand)
        modes = OPS[mn]
        value = 0
        if expr:
            try:
                value = self.value(expr, strict)
                known = True
            except _Undefined:
                known = False
            if mode in ZP_FORM:
                if lineno not in decisions:
                    zp = ZP_FORM[mode]
                    decisions[lineno] = zp if (known and 0 <= value <= 0xFF and zp in modes) else mode
                mode = decisions[lineno]
        if mode not in modes:
            raise AsmError(f"{mn} has no {mode} form")
        out[pc] = modes[mode]
        size = SIZE[mode]
        if mode == "rel":
            offset = value - (pc + 2)
            if strict and not -128 <= offset <= 127:
                raise AsmError(f"branch out of range ({offset})")
            out[pc + 1] = offset & 0xFF
        elif size == 2:
            if strict and not 0 <= value <= 0xFF and mode != "imm":
                raise AsmError(f"operand {value:#x} doesn't fit in a byte")
            out[pc + 1] = value & 0xFF
        elif size == 3:
            out[pc + 1], out[pc + 2] = value & 0xFF, (value >> 8) & 0xFF
        return pc + size


def assemble(source: str) -> tuple[dict[int, int], dict[str, int]]:
    a = Assembler()
    out = a.assemble(source)
    return out, a.symbols
