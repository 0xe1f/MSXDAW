---
name: konami-msx-disasm
description: >-
  Methodology for a byte-exact, commented, reassemblable disassembly of a
  Konami MSX/MSX2 MegaROM (Konami4 / SCC and similar). Use when disassembling,
  annotating, naming labels, or deciding whether a helper belongs in MSXDAW
  or in the game repo.
---

# Konami MSX disassembly

Workbench: `tools/workbench` (this repo as a submodule). Game-specific dumpers
stay in the game’s `tools/`. Read the game’s `docs/progress.md` and
`docs/game-notes.md` plus `workbench.cfg` before assuming a mapper layout.

## Placement

If a helper would apply to a **second** MSX/Konami cart, put it in MSXDAW and
run `bin/add-skill` / `bin/install-skills`. If it names this ROM’s stems, RAM,
banks, or dumpers, keep it in the game. No ROM-specific addresses in DAW skills.

## Non-negotiables

- **Byte-exact round-trip at every step.** The build must reproduce the original
  ROM byte-for-byte (`make verify` checks SHA-1 against a committed
  `<Game>.sha1`). Run it after every edit. Never commit a change that breaks it.
  An original ROM dump is not required to assemble or verify.
- **No leftover binaries.** End state is labelled `.asm` for every ROM byte
  (code and identified data). Banks start as `INCBIN` and graduate; PNG/WAV
  catalogues are previews, not assemble source. Don’t mass-convert unknown
  blobs to opaque `db`. Peel: `msx-code-data`.
- Assembler = sjasmplus, disassembler = z80dasm.

## Bank vs segment

- **Bank** — 8 KiB mapper unit.
- **CPU page** — 16 KiB MSX slot page.
- **Window file** — one `.asm` (and matching `.blocks`) for every set of
  banks this cart maps together. See below.
- Do not say **segment** in new text.

Mapper first: size, bank count, switch addresses, which pages are switchable.
Konami4: typically `6000`/`8000`/`A000` (page `4000-5FFF` often fixed). Konami
SCC: `5000`/`7000`/`9000`/`B000`; SCC at `9800` after `3F` → `9000`. Document
it at the top of `<Game>.asm`. Do not copy another game’s window grouping.

## Window files (combine contiguous banks)

Bootstrap is one `banks/bankNN.asm` per 8 KiB (`msx-bootstrap`). That split is
scaffold. Once paging helpers are named (`page_triplet` / pair / A000-only
wrappers → `bank_org`), **merge every set of banks that helper maps as
consecutive mapper ids into consecutive CPU pages** into one window file,
one `PHASE` covering the whole range.

A Konami triplet `ld a,N / write / inc a / write / inc a / write` into
6000/8000/A000 is one window (banks N, N+1, N+2). An 8000+A000 pair is one
window. A bank that is *also* switched A000-only still lives in its triplet
file. Do **not** merge two pagers just because they reuse the same CPU
addresses at different times — that is a `MODULE`, not one file. Bank 0 stays
its own window when page 4000–5FFF is never remapped.

Stem: `banks_` + concatenated **unpadded hex** ids in CPU order
(`banks_123`, `banks_9a`, `banks_bcd`, `banks_ef`). Same stem for
`banks_<stem>.asm` and `banks_<stem>.blocks`. Section the `.blocks` file per
8 KiB (`; bank 1 @ 0x6000`); `regen-bank.sh` keeps only blocks whose **start**
falls in the slice being disassembled (`msx-regen`, `msx-code-data`).

Later windows that occupy a CPU range already used by an earlier window wrap
the INCLUDE in one `MODULE` (not one MODULE per 8 KiB) so z80dasm `lXXXXh`
names do not collide. The first window in that range can stay global. Do not
put those overlapping addresses in `msx.sym`.

Fold generated 8 KiB listings into the window file by hand; `make verify`.
`.blocks` / peel: `msx-code-data`.

## Conventions

- Never leave z80dasm `;addr bytes ascii` tails in committed `.asm`.
- Annotate per-opcode (column 32). Rename `sub_XXXXh`/`lXXXXh` when confirmed;
  keep the ROM address in the block header; add the name to `msx.sym`.
- Casing: `UPPER_SNAKE` only for MSX BIOS and macro-like helpers (`DISPATCH_A`);
  `lower_snake` for game code/data. Numeric type ids live in `INCLUDE`d `.inc`
  files, never `msx.sym`. Jump tables stay next to their dispatcher.
- Identified bulky data may be `banks/data/<stem>.asm`, `INCLUDE`d from the
  bank or window file (`msx-code-data`). Do not mkdir `banks/data/` until
  the first such peel. Type ids stay in `.inc`, not `data/`.
- Identified **1bpp** pixel rows are `defb %xxxxxxxx` (MSB = left, one row
  per line): sprites, SCREEN 1/2 tiles, fonts, unused copies. Convert as
  soon as the layout is known. Do not leave 1bpp as hex because a sheet is
  not dumped yet (`msx-gfx-sheets`).
- A symbol in an immediate operand is usually a lie (`ld de,CHKRAM` was `ld de,0`).
  Only `call`/`jp`/`jr` targets are real references.
- `msx.sym` is flat; the ROM is banked. `bank_sym.py` filters per CPU window.

Text is often `(ASCII - offset)`. Use an sjasmplus `MACRO` so source stays
readable; space often becomes `0x00`. Quoted `defb` strings use sjasmplus
escapes (`\"`, `\\`). Do not split a quote out as `022h`. Single-quoted
strings do not take backslash (`'"'` is a quote byte).

## Konami idioms (patterns)

- Inline word-table dispatch by index in A (`DISPATCH_A`). Check for `dec a`
  (off-by-one) before the dispatch.
- Consecutive-bank **triplet pager**: A = first bank; write A, `inc a`, write,
  `inc a`, write to the three switchable mapper ports. Wrappers are
  `ld a,N / jr shared_tail`. Current triplet is often mirrored in work RAM
  and restored after a far call. That helper is the ground truth for
  `bank_org` (`msx-code-data`).
- A paged bank often starts with `jp`/`jp`/`jp` matching `call 6000h` /
  `6003h` / `6006h` from the resident bank after paging that triplet.
- A jump table at the end of a bank can continue into the next page. Mapper
  switch addresses are typically write-only; a *read* returns the ROM currently
  paged there.
- Spawn-init table ≠ per-frame tick table.
- Packed room object lists are often actor type ids. A second packed list in
  the same bank may use a **different** grammar — don’t reuse the first decoder.
- MSX SAT Y is the line above the sprite; writers often `dec a` into SAT.
- RNG via `ld a,r`. Packed BCD via `daa`.
- A boot-time slot scan (`EXPTBL` / `RDSLT`) is usually companion-hardware
  detection (Konami Game Master is the common fingerprint: RC BCD + `0xAA` at
  the end of a 16K page), not a re-entrancy flag.
- Subsystem state often sits in one contiguous RAM block. Snapshot-diff, then
  `romscan xref`.

## Maps

Level data is layered pointer tables. Room-to-room movement is usually
**table-driven**, not arithmetic. A connectivity graph is a **navigation**
graph, not a spatial one — don’t reconstruct geography from it with BFS.
If the game shows a map, decode that table. Render ROM-derived structure to
an image and compare to the real game. When two mechanisms are plausible,
render both. Watch the RAM the feature is supposed to fill.

## Cost

Reuse `regen-bank.sh` and `romscan.py`. Don’t grep leftover `.bin` or write
ad-hoc xref python. Runtime tracing: `msx-cocoamsx`. Early code/data split
(`.blocks`, bank roles, illegal-sequence seeds): `msx-code-data`.
