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
`bank_org`. Optional `.blocks` marks code vs data (rendering only). How to seed it:
`msx-code-data`.

Writes gitignored scratch:

- `generated/<prefix>NN.generated.asm` — listing comments stripped; **fold this**
- `generated/<prefix>NN.raw.asm` — address/opcode listing; temporary reference

Never copy the generated file over annotated source. Never commit z80dasm
`;addr bytes ascii` tails. `strip-listing.py` is the safety net.

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
