# DISASMTRACE helpers

Build and run the instrumented CocoaMSX in this tree (`-DDISASMTRACE`).
F9 dumps a work-RAM snapshot; F8 toggles auto-snap. `EXEC` / `WATCH` log
executed PCs and memory writes tagged with the paged ROM bank.

The game ROM, snapshot file, and exec/watch log stay in the **game** repo
(found via `workbench.cfg`, or `GAME=` / legacy `VK=`).

```
tools/disasm/build-cocoamsx.sh
WATCH=ce00-ce15 tools/disasm/trace-run.sh
tools/disasm/snapdiff.py generated/disasmsnap.bin
```

`SOFTGL=1` (the default) forces Apple software GL; required on Apple Silicon.
Grant Input Monitoring to the built `.app` once.
