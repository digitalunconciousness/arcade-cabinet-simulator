# Sim Control Protocol v1

How the app (Stage 2 on) and tools talk to the `cabsim` plugin inside MAME (`plugin/cabsim/server.lua`, ADR-0013).

## Transport

- TCP on `127.0.0.1`, on the port given to MAME in the environment variable `CABSIM_PORT`. The plugin listens only when
  that variable is set.
- Newline-terminated JSON objects in both directions, UTF-8. One reply per request, in order.
- Requests run on MAME's periodic callback, which also runs while the machine is paused.
- Stage 1 serves one client per MAME session. Reconnects and frame streaming come with the Stage 2 spike.

## Requests and replies

A request is `{"cmd": "<name>", ...}`. Every reply has `ok`. A request may carry `req` (any JSON value); the reply
echoes it back. A failed request replies `{"ok": false, "error": "<text>"}`, and an unknown command does the same.

| cmd | arguments | reply |
|---|---|---|
| `hello` | | `protocol` (`"scp/1"`), `app`, `version`, `romset` |
| `state` | | `romset`, `paused`, `frame` (MAME's frame number on the current machine), `faults` |
| `pause`, `resume` | | as `state` |
| `reset` | `kind`: `"soft"` (default) or `"hard"` (power cycle) | `reset` |
| `fault.apply` | `primitive`, `params` | `id`, `tier` |
| `fault.clear` | `id` | `ok` is false if no such fault |
| `fault.clear_all` | | `cleared` (count) |
| `fault.list` | | `faults`: `[{id, primitive, params, tier}]` |
| `input.button` | `port`, `field`, `down` | `down` (after input faults) |
| `input.analog_delta` | `port`, `field`, `delta` | `position` (after input faults) |

Primitives and their parameters are listed in `tools/cabsim/README.md` and documented in `plugin/cabsim/primitives.lua`.
Faults stay active across resets, including power cycles, until cleared.

## Example

```
> {"cmd":"hello","req":1}
< {"ok":true,"protocol":"scp/1","app":"mame","version":"0.287","romset":"centiped3","req":1}
> {"cmd":"fault.apply","primitive":"reg_read_override","params":{"space":":maincpu","addr":4106,"rule":{"and_mask":253}},"req":2}
< {"ok":true,"id":1,"tier":"A","req":2}
> {"cmd":"input.analog_delta","port":":TRACK0_X","field":"Trackball X","delta":3,"req":3}
< {"ok":true,"position":3,"req":3}
> {"cmd":"fault.clear","id":1,"req":4}
< {"ok":true,"id":1,"req":4}
```

`tools/cabsim/scp_smoke.py` exercises all of this against a running MAME, in CI too.

## Versioning

Adding a command or an optional argument keeps `scp/1`. Changing or removing one makes it `scp/2`, and `hello` lets a
client refuse a protocol it doesn't speak.
