# Devices/BAD_RAM_CELL
> The full reference is at [`docs/devices/bad_ram_cell.md`](../../docs/devices/bad_ram_cell.md).
> This wiki page is a one-screen summary; keep them in sync when the
> device changes.
A 16 × 1 SRAM with first-class support for a stuck-at fault that
affects exactly one configurable address. The rest of the chip behaves
like a normal SRAM. Use this for single-cell RAM-decay symptoms;
`FAULT_BUFFER` on the data line would fault every read, not just one
address.
## Modes
| MODE | Name      | Behavior at BAD_ADDR                                |
|------|-----------|-----------------------------------------------------|
| 0    | NORMAL    | All 16 cells behave like normal SRAM.               |
| 1    | STUCK_HI  | Reads return 1; writes are dropped.                 |
| 2    | STUCK_LO  | Reads return 0; writes are dropped.                 |
| 3    | FLIP      | Reads return stored bit XOR 1; writes are dropped.  |
## Pin map
- `A0..A3` 4 address inputs (16 cells)
- `CEQ`    chip enable, active-low
- `RWQ`    read/write, low = write
- `DI`     data input (1 bit)
- `DO`     data output (1 bit, 250 ns access delay)
- `VCC`    auto-connected
- `GND`    auto-connected
## Parameters
- `BAD_ADDR` (int, default 0) — which cell (0..15) is faulty.
- `MODE` (int, default 0) — runtime fault mode.
## See also
- [docs/devices/bad_ram_cell.md](../../docs/devices/bad_ram_cell.md) — full reference.
- [tests/netlist/centiped/ram_region.cpp](../../tests/netlist/centiped/ram_region.cpp) — verification harness.
- [Phase-5.5-RAM-Region](../Phases/Phase-5.5-RAM-Region.md) — phase notes.
- [Devices/FAULT_BUFFER](FAULT_BUFFER.md) — pin-level counterpart.
