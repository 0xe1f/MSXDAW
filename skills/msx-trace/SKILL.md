---
name: msx-trace
description: >-
  Build and run the DISASMTRACE CocoaMSX in tools/workbench/cocoamsx. F9 RAM
  snapshots, F8 auto-snap, EXEC/WATCH logs tagged with the paged ROM bank.
  Use when tracing, snapshot-diffing, or watching work-RAM.
---

# MSXDAW CocoaMSX trace

The instrumented emulator lives in `tools/workbench/cocoamsx/` (or
`~/code/msxdaw/cocoamsx/` in the canonical clone). ROM, snapshot file, and
logs stay in the **game** repo (`generated/`).

```
tools/workbench/cocoamsx/tools/disasm/build-cocoamsx.sh
WATCH=ce00-ce15 tools/workbench/cocoamsx/tools/disasm/trace-run.sh
tools/workbench/cocoamsx/tools/disasm/snapdiff.py generated/disasmsnap.bin
```

`trace-run.sh` finds the game via `workbench.cfg` (cwd or `GAME=`). Pass a ROM
path to override.

`SOFTGL=1` (default) forces Apple software GL; required on Apple Silicon.
Grant Input Monitoring to the built `.app` once.
