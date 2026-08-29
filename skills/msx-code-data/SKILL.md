---
name: msx-code-data
description: >-
  Split code from data early in a banked Z80 MSX disassembly: .blocks maps,
  bank classification, inline DISPATCH_A tables, illegal-sequence seeds.
  Use after msx-bootstrap on a new cart, when writing banks/*.blocks,
  converting fake instructions to defb/defw, or asking what is code vs data.
---

# Split code vs data

Unmarked data desyncs z80dasm for every byte after it until the next obvious
entry. Mark a region as data **before** naming the table. `.blocks` only
changes rendering, never bytes. Naming: `konami-msx-disasm`. Regen: `msx-regen`.
`make verify` after every edit (`konami-msx-disasm`).

## After bootstrap

`msx-bootstrap` named bank 0 boot (header, init, `H.TIMI`, switchers). Next:

1. Decode paging helpers. Those writes are the ground truth for what each
   other 8 KiB bank **is** (play code, tileset, map, title gfx, sound).
2. Entropy / opcode histogram is a hint (`0xCD`/`0xC3`/`0xDD` vs
   low-entropy zero-heavy 4bpp). Mixed banks exist — do not call a map or
   PSG-driver bank “graphics” from entropy alone.
3. Seed `.blocks` from the mechanical list below. Regen **code** banks with
   the block file. Leave gfx / packed-PSG payload banks as `INCBIN` until
   the consumer (`rle_dec`, list loader, PSG interpreter) is found.
4. After the first raw regen, grep `generated/*.raw.asm` for
   `;illegal sequence` and for nonsense `jp` / `ret cc` / `sbc a,*` runs.
   Each hit is a `.blocks` seed.

Do not disassemble a tileset or RLE bank as code.

## `.blocks`

One file per bank (`banks/bankNN.blocks`) or per window file. `regen-bank.sh`
keeps only blocks whose **start** falls in the 8 KiB being disassembled.
Names must not collide with in-source labels (z80dasm emits `NAME_start`).

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

## Consumers, then scan

Once `rle_dec` / the text blit / the PSG interpreter is named in bank 0,
scan other banks for well-formed streams (`msx-gfx` RLE grammar; `0x00`
end). Those regions are data. `gfxview.py` on a low-entropy bank is a
preview, not a split.

Companion: `msx-bootstrap`, `msx-regen`, `msx-romscan`, `msx-gfx`,
`konami-msx-disasm`.
