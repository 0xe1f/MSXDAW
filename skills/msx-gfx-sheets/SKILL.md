---
name: msx-gfx-sheets
description: >-
  Build labelled PNG contact sheets for MSX tiles, metatiles, hardware sprites,
  fonts, and palettes. One atom per cell, hex header, in-game palette. Use when
  adding gfx catalogue sheets, make gfx, or tile/sprite/font/palette previews.
  Game dumpers live in the game repo and import pngwrite.py.
---

# MSX gfx contact sheets (guidelines)

PNG is preview only. Compressed / labelled `.asm` bytes stay authoritative
(`make verify`). Implement the dumper in the **game** repo (`tools/` + `make gfx`);
import `tools/workbench/msx/pngwrite.py`. No PIL/Pillow.

## Directories

| Dir | Contents |
|-----|----------|
| `gfx/tilesets/` | 4bpp playfield / HUD tiles |
| `gfx/sprites/` | packed 1bpp sprite planes |
| `gfx/fonts/` | 1bpp glyph sheets |
| `gfx/palettes/` | palette_apply swatches (not tiles) |
| `gfx/metatiles/` | composed metatile defs / room streams |
| `gfx/` | composites only |

Do not put composites or fonts in `sprites/`. Do not put palette swatches in `tilesets/`.

## Cell

One atom per cell, uniform grid. Do not pack a SAT figure or animation into one
catalogue cell (that is a composite sheet).

Typical atoms: 8×8 4bpp tile (32 bytes); 16×16 4bpp; 16×16 1bpp sprite plane
(32 bytes); 8×8 1bpp glyph (8 bytes); 3-byte palette record as an 8×8 swatch.

## Palette

On-pixels use the VDP index the game writes for that atom when it is on
screen: SAT colour low nibble, `copy_tiles` C (on = low, off = high), dest
nibbles. Load that object’s `palette_list` (or the play palette it shares).
Do not pick an unused slot, even/odd pair, or greyscale as a preview ink.

Hardware sprites are usually two SAT colour planes (a CC pair). Keep **one
plane per cell**. Paint plane 0 with the first colour and plane 1 with the
second. Do not overlay the pair (the VDP ORs indices; a catalogue cell is
one plane).

Transparent / unused pixels are a visible off-colour so cell bounds stay
readable. That off-colour is not a palette index. Index 0 stays off except
on palette sheets, which paint the table’s own RGB.

## Header

Dark band above every cell. Identifier is **4 uppercase hex digits, no `0x`**
(CPU address of that atom, or a 2-digit glyph id). Unique per cell. Do not
reuse a dest every stream shares.

## Source form

- **1bpp pixel data** (tiles, sprites, fonts, unused copies): `defb %xxxxxxxx`
  (MSB = left, one 8-pixel row per line) as soon as the bytes are known to be
  1bpp. Do not leave identified 1bpp as hex `0xxh` rows. A PNG is not required
  first; convert when the consumer or `gfxview` layout is known.
- **4bpp** tiles: hex nibble-rows.
- Packed RLE *pixel* bytes may use `%`; control bytes stay hex.
  Nametable ids, SAT seeds, and colour bytes stay hex.

`gfx/<kind>/<stem>.png` ↔ `banks/data/<stem>.asm`. Create that dir on the
first peel (`msx-code-data`), not for a sheet that has no asm yet. Add /
rename / delete the asm → the PNG goes with it. `make gfx` regenerates.
