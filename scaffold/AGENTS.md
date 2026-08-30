# __GAME__

This is an [MSXDAW](https://github.com/) game repo (MSX Disassembly Workbench).

- Workbench (tools, generic skills): `tools/workbench` (git submodule of `~/code/msxdaw`).
- Generic skills live in `tools/workbench/skills/` and are linked into this repo's `.cursor/skills/` (`tools/workbench/bin/install-skills`). After pulling workbench, re-run it so new skills are linked and removed ones are dropped. Never `~/.cursor/skills`.
- Game-only skills live in `.agents/skills/` (`__GAME__-*` / cart-specific). Do not copy DAW skills here.

**Placement:** if a helper would apply to a second MSX/Konami cart, put it in msxdaw. If it names this ROM’s stems, RAM, banks, or dumpers, keep it in this repo.

**Byte-exact round-trip at every step.** `make verify` must match the committed
`<Game>.sha1`. Run it after every edit. Never commit a change that breaks it.
An original ROM dump is not required to assemble or verify.

**End state.** Every ROM byte is labelled `.asm`. Leftover `INCBIN` is scaffold
only (`msx-code-data`).

Default source split is **one file per 8 KiB mapper bank** (`banks/bank00.asm`)
until paging helpers are named. Then combine banks this cart maps together
into one window file per group (`konami-msx-disasm`). Say **bank**, not segment.
