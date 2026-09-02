---
name: msx-code-data
description: >-
  Split code from data early in a banked Z80 MSX disassembly: .blocks maps,
  bank classification, inline DISPATCH_A tables, illegal-sequence seeds,
  peeling identified blobs into banks/data. Use after msx-bootstrap on a
  new cart, when writing banks/*.blocks or window banks_*.blocks, converting
  fake instructions to defb/defw, asking what is code vs data, or moving
  tables/gfx out of a bank file.
---

# Split code vs data

Unmarked data desyncs z80dasm for every byte after it until the next obvious
entry. Mark a region as data **before** naming the table. `.blocks` only
changes rendering, never bytes. Naming: `konami-msx-disasm`. Regen: `msx-regen`.
`make verify` after every edit (`konami-msx-disasm`).

## After bootstrap

`msx-bootstrap` named bank 0 boot (header, init, `H.TIMI`, switchers). Next:

1. Decode paging helpers. Those writes are the ground truth for what each
   other 8 KiB bank **is** (play code, tileset, map, title gfx, sound) and
   which banks are mapped **together**. Combine those into window files
   (`konami-msx-disasm`); do not leave a known triplet as three `bankNN.asm`.
2. Entropy / opcode histogram is a hint (`0xCD`/`0xC3`/`0xDD` vs
   low-entropy zero-heavy 4bpp). Mixed banks exist — do not call a map or
   PSG-driver bank “graphics” from entropy alone.
3. Seed `.blocks` from the mechanical list below. Regen **code** banks with
   the block file. Leave gfx / packed-PSG payload as `INCBIN` until the
   consumer (RLE decoder, list loader, PSG interpreter) is found, then fold
   as labelled `.asm` (not z80dasm). End state: no leftover `.bin`.
4. After the first raw regen, grep `generated/*.raw.asm` for
   `;illegal sequence` and for nonsense `jp` / `ret cc` / `sbc a,*` runs.
   Each hit is a `.blocks` seed.

Do not disassemble a tileset or RLE bank as code.

## `.blocks`

One file per **window**, same stem as the `.asm` (`banks/banks_123.blocks`).
Until windows exist, one file per 8 KiB (`banks/bank00.blocks`) is fine.
`regen-bank.sh` keeps only blocks whose **start** falls in the 8 KiB being
disassembled — pass the window `.blocks` for every slice in that window.
Names must not collide with in-source labels (z80dasm emits `NAME_start`).
Section the file per 8 KiB (`; bank 1 @ 0x6000`).

```
rom_header: start 0x4000 end 0x4010 type bytedata
foo_tbl:    start 0xADDR end 0xADDR type worddata
```

`type` is `bytedata` or `worddata`. Bound a table by the next real routine, a
range check on A, or a `dec a` / `sub base` immediately before the dispatcher
(off-by-one: id N is `table[N-1]`).

## Seed mechanically (day one)

- **AB header** (16 bytes at `0x4000`) is never code. Konami often parks a
  Game Master option table immediately after it — that island mis-aligns
  the IRQ if decoded as instructions.
- Every `call DISPATCH_A` (or the local pop-return-address dispatcher) is
  followed by an inline **word** table. Same for `ld hl/de,imm` then
  `ADD_HL_A` / `ADD_DE_A`: the immediate is a table start. `romscan table`
  decodes it; `--index-base 1` when the dispatcher does `dec a`.
- A jump table at the **end of a bank may continue into the next page**.
  Mapper switch addresses are typically write-only; a *read* returns the
  ROM currently paged there. Alignment follows the table, not the page
  (odd start + pad → do not `defw` from the page base).
- Layout / text streams often use `0xFE` = next row/field, `0xFF` = end.
  Finding the blit in bank 0 lets `romscan xref` list every stream.

## Do not

- Wait to understand a table before marking it. Un-poisoning the
  following code is the point.
- Require a gap after `ret`. `table[0]` may be `0xC9` that is also the
  previous routine’s return.
- Treat “never executed” as data. Coverage misses Game Master, credits,
  unused types. Broad `EXEC` is not a code/data map (`msx-cocoamsx`).
  Coverage **confirms** a region is code; it does not prove the rest is data.
- Reuse the first packed-list decoder on the next blob in the same bank.
  A second list often has a different grammar.
- Mass-convert an unknown bank to opaque `db`.

## Peel (identified blobs)

`INCBIN` is a holding pattern. Once a consumer and a grammar exist, fold the
blob as labelled `defb`/`defw`. Identified **1bpp pixels** (tiles, sprites,
fonts, leftover copies) are `defb %xxxxxxxx` immediately — not after a PNG,
not only when the file is a catalogue stem (`msx-gfx-sheets`). Hex `0xxh`
rows are for unknown or non-pixel bytes. Every ROM byte ends as labelled
`.asm`.

Leave it in the bank file, or as `banks/bankNN.<stem>.inc`, until it is a
named catalogue of its own. Then `banks/data/<stem>.asm` and `INCLUDE` from
the bank or window file. PNG pairing: `msx-gfx-sheets`.

Do not create `banks/data/` speculatively. Do not peel jump tables that sit
next to their dispatcher, or move type-id `.inc` files into `data/`. Do not
z80dasm a tileset / RLE / packed-PSG payload.

## Consumers, then scan

Once the RLE decoder / the text blit / the PSG interpreter is named in bank 0,
scan other banks for well-formed streams (`msx-gfx` RLE grammar; `0x00`
end). Those regions are data. `gfxview.py` on a low-entropy bank is a
preview, not a split.

Companion: `msx-bootstrap`, `msx-regen`, `msx-romscan`, `msx-gfx`,
`konami-msx-disasm`.
