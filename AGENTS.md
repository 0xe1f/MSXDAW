# MSXDAW

MSX Disassembly Workbench. Game repos vendor this tree as `tools/workbench`.

**Placement:** generic MSX / shared Konami formats → this repo. ROM-specific
stems, RAM maps, bank windows, dumpers → the game’s `tools/` and `.agents/skills/`.

**Banks, not segments.** Scaffold is one `banks/bankNN.asm` per 8 KiB. Once
paging helpers show which banks are mapped together, combine those into one
window file (`konami-msx-disasm`). Linear 16/32 KiB carts have no pager —
do not copy a Konami window split. New game repo: `msx-scaffold`.

**Byte-exact round-trip.** Game repos run `make verify` after every edit against
a committed `<Game>.sha1`. Never commit a break. An original ROM dump is not
required to assemble or verify.

**End state.** Every ROM byte is labelled `.asm`. Leftover `INCBIN` bins are
scaffold only. Do not mass-convert unknown blobs to opaque `db` (`msx-code-data`).
Identified 1bpp pixel data is `defb %xxxxxxxx` as soon as it is known
(`msx-gfx-sheets`); hex rows are not a holding form for sprites or tiles.
Per-opcode comments (column 32) when the line is in front of you and the
meaning is confirmed — a cheap win, not a later pass (`konami-msx-disasm`).

**Skills:** `bin/add-skill` (always runs `bin/install-skills`). Link each
`skills/<name>` into the current project's `.cursor/skills/` and remove
stale workbench links after a rename or delete. Never `~/.cursor/skills`.
Agents in a game repo must follow `tools/workbench/skills/` in addition to
the game’s `.agents/skills/`. Run `bin/install-skills` after pulling
workbench when skills were added or removed. WAV catalogues (`make music` /
`make sfx`) follow `msx-psg-catalogue`. Konami renderers are `konami-psg`;
Taito `psg_play` is `msx/taitoplay.py`. Catalogue AY generators match
CocoaMSX `AY8910.c` (in `konami/psgplay.py`).

**Docs:** record changes to this tree (tools, skills, `cocoamsx/`) **here** —
this file, `README.md`, `skills/<name>/SKILL.md`, and the tool’s own README
(`cocoamsx/tools/disasm/README.md` for the research display). A game’s
`docs/progress.md` is ROM findings only; do not dump emulator how-to there.

When adding a tool, weigh it: second cart would use it → here; only this ROM →
the game.
