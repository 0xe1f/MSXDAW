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

Transparent / unused pixels are a visible off-colour so cell bounds stay
readable. Index 0 stays off except on palette sheets, which paint the table’s
own RGB.

## Header

Dark band above every cell. Identifier is **4 uppercase hex digits, no `0x`**
(CPU address of that atom, or a 2-digit glyph id). Unique per cell. Do not
reuse a dest every stream shares.

## Source form

- **1bpp** identified sheets: `defb %xxxxxxxx` (MSB = left, one row per line).
- **4bpp** tiles: hex nibble-rows.
- Packed RLE *pixel* bytes may use `%`; control bytes stay hex.

`gfx/<kind>/<stem>.png` ↔ `segments/data/<stem>.asm` or `banks/data/<stem>.asm`.
Add / rename / delete the asm → the PNG goes with it. `make gfx` regenerates.

Paint with the VDP palette the game uses when that object is on screen. Do not
invent even/odd inks or greyscale stand-ins. Do not CC-overlay two SAT planes
on a catalogue sheet (overlap is OR of colour indices).
