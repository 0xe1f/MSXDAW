# CocoaMSX (MSXDAW fork)

This is **not** upstream [CocoaMSX](https://github.com/CocoaMSX/CocoaMSX).
It is a modified tree for **AI-guided tooling**: a live MSX display an agent
can launch, seek, peek, and drive from a text socket, while a human still
plays in the window.

Based on CocoaMSX 1.61 / [blueMSX](http://www.bluemsx.com/). Keep the original
copyright notices. Do not treat this binary as a general-purpose emulator
UI — Preferences, Sparkle updates, video filters, and the old OpenGL present
path are stripped or unhooked on purpose.

## What this fork adds

- Nearest-neighbor present (GPU CALayer by default; CPU `drawRect` fallback)
- JSON config (`cocoamsx.json.example`) + SIGHUP / `reload-config`
- Unix socket + `tools/disasm/cocoamsx-ctl` (peek, watch, snap, keys, savestate)
- `DISASMTRACE` (F8/F9 RAM snapshots, EXEC/WATCH logs)
- Window-focused AppKit keys only (no Input Monitoring)
- Emulation keeps running in the background (stock pause-when-unfocused is off)

Build, launch, and control: **[tools/disasm/README.md](tools/disasm/README.md)**.
Agent skill: `msx-cocoamsx`. Further emulator changes are documented there and
in that skill, not in a game repo’s `docs/`.

```
tools/disasm/build-cocoamsx.sh
tools/disasm/trace-run.sh /path/to/game.rom
tools/disasm/cocoamsx-ctl peek c000
```

Game ROMs, snapshot files, and logs stay in the **game** repo (`workbench.cfg`).
Do not copy ROMs into this tree.

Upstream project: [cocoamsx.com](http://www.cocoamsx.com) /
[github.com/CocoaMSX/CocoaMSX](https://github.com/CocoaMSX/CocoaMSX).
