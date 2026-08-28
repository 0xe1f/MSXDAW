---
name: msx-gfx
description: >-
  Inspect MSX graphics: 1bpp/4bpp ASCII via gfxview.py, PNG via pngwrite.py,
  and Konami VRAM RLE (rledec.py / rleenc.py). Use when hunting sprites, tiles,
  fonts, SCREEN 5 bitmaps, packed RLE streams, or identifying graphics at a
  ROM or VRAM offset. Not for labelled PNG catalogue sheets (msx-gfx-sheets).
---

# MSX gfx (ASCII / RLE)

File offsets are **ROM file** offsets unless the region is already a flat dump.
Committed source keeps original packed bytes; PNG/`rleenc` is preview or modding.

## Hunt by eye

```
tools/workbench/msx/gfxview.py <file> <hex-off> [--count N] [--size 8|16] [--cols C] [--bpp 1|4]
tools/workbench/msx/gfxview.py <file> <hex-off> --bpp 4 --raw --width W --rows R
```

| `--bpp` | Use for | Layout |
|---|---|---|
| `1` | hardware sprites, SCREEN 1/2 patterns | 8x8 = 8 bytes/row; 16x16 = 32 bytes, TL BL TR BR |
| `4` | SCREEN 5/7 bitmaps | N rows of N/2 bytes, high nibble = left pixel |

## Konami VRAM RLE

| Op | Meaning |
|---|---|
| `00` | end |
| `80 lo hi` | VRAM write pointer = `hi<<8\|lo` |
| `01..7F` | RUN: next byte repeated N times |
| `81..FF` | LITERAL: copy `(N & 0x7F)` bytes |

```
tools/workbench/konami/rledec.py <rom> <src-hex> [--dest 0xF800] [--out out.bin]
tools/workbench/konami/rleenc.py flat.bin [--out packed.rle]
```

`rleenc` is not always byte-exact vs original streams. `pngwrite.py` is a
library (`write_rgb`); game sheet dumpers import it. Contact sheets: `msx-gfx-sheets`.
