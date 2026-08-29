# MSXDAW

MSX Disassembly Workbench. Game repos vendor this tree as `tools/workbench`.

**Placement:** generic MSX / shared Konami formats → this repo. ROM-specific
stems, RAM maps, bank windows, dumpers → the game’s `tools/` and `.agents/skills/`.

**Banks, not segments.** One `banks/bankNN.asm` per 8 KiB mapper unit unless this
cart’s mapper schedule justifies a window file.

**Byte-exact round-trip.** Game repos run `make verify` after every edit against
a committed `<Game>.sha1`. Never commit a break. An original ROM dump is not
required to assemble or verify.

**Skills:** `bin/add-skill` (always runs `bin/install-skills`). Do not leave a
new `skills/<name>` without the `~/.cursor/skills` symlink. Agents in a game
repo must follow `tools/workbench/skills/` in addition to the game’s
`.agents/skills/`.

**Docs:** record changes to this tree (tools, skills, `cocoamsx/`) **here** —
this file, `README.md`, `skills/<name>/SKILL.md`, and the tool’s own README
(`cocoamsx/tools/disasm/README.md` for the research display). A game’s
`docs/progress.md` is ROM findings only; do not dump emulator how-to there.

When adding a tool, weigh it: second cart would use it → here; only this ROM →
the game.
