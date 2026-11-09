# Stage 0 evidence

Output of `tools/audit/run_audit.py` and `tools/audit/netlist_standalone.py`. It was produced on 2026-11-09 with MAME 0.287
(`mame0287` plus `patches/0001`–`0003`), romset `centiped3`, headless (`-video none -sound none -nothrottle`) on Linux.
The summary and per-fault tables are in `docs/FAULT_AUDIT.md`.

| File | What it holds |
|---|---|
| `inventory.json` | every legacy fault the audit ran, and the HTTP call that applies it |
| `results.json` | one record per fault: verdict, frame and RAM differences, the plugin commands the fault sent and the replies |
| `baseline_hashes.txt` | the screen hash of every frame (0–1200) of the baseline run; the second baseline run matched it exactly |
| `runs/<fault>.json` | the full log of one run: every HTTP call to the legacy server and every plugin command and reply |
| `runs/baseline.json` | the same for the baseline (no fault, same input) |
| `runs/netlist.json` | `/api/run` waveforms for every sync-generator pin and mode |
| `runs/netlist_standalone.json` | the standalone nltool harnesses in `tests/netlist/` |
| `images/baseline_f<frame>.png` | baseline screens at the checkpoints (600, 660, 900, 1200) |
| `images/<fault>_f<frame>.png` | the faulted screen at the first checkpoint where it differs, plus `_zoom.png`: baseline left, faulted right, 8× around the changed pixels |

Screens are MAME's raw screen bitmap, rotated 90° to the cabinet's upright orientation. No ROM data is stored here.
