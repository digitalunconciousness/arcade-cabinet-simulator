# Devices/FAULT_BUFFER
> The full reference is at [`docs/devices/fault_buffer.md`](../../docs/devices/fault_buffer.md).
> This wiki page is a one-screen summary; keep them in sync when the
> device changes.
A transparent buffer with runtime fault injection. Inserted by the
auto-instrumentation preprocessor on every fault-eligible netlist pin.
## Modes
| MODE | Name      | Behavior                                      |
|------|-----------|-----------------------------------------------|
| 0    | NORMAL    | Y follows A (1 ns prop delay).                |
| 1    | STUCK_HI  | Y driven high regardless of A.                |
| 2    | STUCK_LO  | Y driven low  regardless of A.                |
| 3    | OPEN      | Y high-impedance — pin appears disconnected.  |
## Pin map
- `A`   logic input
- `Y`   tristate output
- `VCC` auto-connected
- `GND` auto-connected
## Parameters
- `MODE` (int, default 0) — runtime fault mode.
- `FORCE_TRISTATE_LOGIC` (logic, default 1) — set to 0 on analog nets so
  OPEN produces real high-Z.
## See also
- [docs/devices/fault_buffer.md](../../docs/devices/fault_buffer.md) — full reference.
- [tests/netlist/fault_buffer_test.cpp](../../tests/netlist/fault_buffer_test.cpp) — verification harness.
- [Phase-1-Fault-Buffer](../Phases/Phase-1-Fault-Buffer.md) — phase notes.
