---
name: msx-regen
description: >-
  Regenerate an 8 KiB mapper bank with z80dasm via tools/workbench/msx/regen-bank.sh,
  emit a per-bank symbol file, and strip listing comments. Use when regenerating
  a bank, running regen-bank.sh, bank_sym.py, strip-listing.py, split-rom.sh,
  folding generated/bankNN.generated.asm, or after renaming labels in msx.sym.
---

# MSX bank regen

Need `z80dasm`, `tools/sjasmplus`, a `workbench.cfg`, and a built `<Game>.rom`
(`make`, or `ROM=`). Run from the **game** repo root. Do not invent a one-off
disassembler.

## Regen one bank

```
tools/workbench/msx/regen-bank.sh <n> [origin-hex] [banks/bankNN.blocks]
```

`<n>` is the 8 KiB bank index (0-based). Origin defaults to `workbench.cfg`
`bank_org`. Optional `.blocks` marks code vs data (rendering only). How to
seed it: `msx-code-data`. Do not regen until `bank_org` matches the pager.

Writes gitignored scratch:

- `generated/<prefix>NN.generated.asm` — listing comments stripped; **fold this**
- `generated/<prefix>NN.raw.asm` — address/opcode listing; temporary reference

Never copy the generated file over annotated source. Never commit z80dasm
`;addr bytes ascii` tails. `strip-listing.py` is the safety net.

## Graduate one leftover bank

1. Confirm CPU origin from paging helpers; put it in `bank_org` and the
   master’s `PHASE` (`msx-code-data`). Do not z80dasm gfx / packed-PSG /
   table-only payload — those stay `INCBIN` until the consumer is named,
   then labelled `.asm` (`msx-code-data` peel).
2. `regen-bank.sh N [origin] [banks/bankNN.blocks]`
3. Grep `generated/<prefix>NN.raw.asm` for `;illegal sequence`.
4. Prepend a bank header; copy the **generated** file (not raw) to
   `banks/bankNN.asm`. Drop z80dasm’s `equ` lines (those symbols live in
   other banks or `bios.inc`). Master: `INCBIN` → `INCLUDE`.
5. BIOS-lie audit on non-`call`/`jp`/`jr` lines. `make verify`, then
   `make banks` (drops the leftover `.bin`).
6. Two banks in the same CPU window (`bank_org` repeat) cannot share
   z80dasm `lXXXXh` / `sub_XXXXh` names. Wrap the INCLUDE in
   `MODULE bankNN` / `ENDMODULE`, or prefix auto labels. Do not put
   those addresses in `msx.sym` (the next bank in that window would
   steal the name).

## Symbols (`msx.sym` is flat, the ROM is banked)

```
tools/workbench/msx/bank_sym.py N
tools/workbench/msx/bank_sym.py --audit
```

Keep new names in the game’s `msx.sym`. Do not split into committed per-bank
`.sym` files.

## Leftover bins

```
tools/workbench/msx/split-rom.sh
```

Extracts unmigrated `banks/bankNN.bin` from the ROM; deletes bins for migrated
banks (`migrated=all` or a `bankNN.asm` exists).

After regen: audit BIOS-name lies on non-`call`/`jp`/`jr` lines. `make verify`
after every edit; never commit a break. Naming: `konami-msx-disasm`.
