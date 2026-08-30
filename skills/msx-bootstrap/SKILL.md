---
name: msx-bootstrap
description: >-
  First session on a new MSX MegaROM: mapper probe, bank split, regen bank 0,
  AB header, H.TIMI / IRQ. Use when scaffolding a game, running probe, or
  starting a disassembly before gameplay systems are named.
---

# MSX bootstrap

1. `workbench.cfg` + mapper (`bin/probe` on the ROM).
2. Extract 8 KiB leftover bins (`split-rom.sh`). Master `INCBIN`s each bank at
   a guessed `PHASE` (0x4000 + (n%4)*0x2000 until proven otherwise).
3. Regen **bank 0** only into `banks/bank00.asm`. One bank, one file.
4. Name boot: `AB` header, init, `H.TIMI` hook, bank-switch helpers.
   `make verify` after the fold. Never leave it red.
5. Stop. Do not invent window files, actor maps, or level formats yet.
   Next session is `msx-code-data` (paging helpers → `bank_org` → `.blocks`).
   After those helpers are named, merge contiguous banks into window files
   (`konami-msx-disasm`).

Konami SCC: switch regs `5000`/`7000`/`9000`/`B000`; page `4000-5FFF` is
switchable; SCC appears at `9800` after `3F` → `9000`. Konami4 is different —
do not copy another game’s “bank 0 is fixed at 4000” as a fact.
