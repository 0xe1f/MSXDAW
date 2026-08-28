# MSXDAW

MSX Disassembly Workbench. Game repos vendor this tree as `tools/workbench`.

**Placement:** generic MSX / shared Konami formats → this repo. ROM-specific
stems, RAM maps, bank windows, dumpers → the game’s `tools/` and `.agents/skills/`.

**Banks, not segments.** One `banks/bankNN.asm` per 8 KiB mapper unit unless this
cart’s mapper schedule justifies a window file.

**Skills:** `bin/add-skill` (always runs `bin/install-skills`). Do not leave a
new `skills/<name>` without the `~/.cursor/skills` symlink.

When adding a tool, weigh it: second cart would use it → here; only this ROM →
the game.
