# `gfxview.py`

Render binary regions as terminal ASCII art to identify MSX patterns, hardware
sprites, tiles, fonts, and linear SCREEN 5/7-style bitmap data. The helper is
read-only and does not require a game repository or `workbench.cfg`.

File offsets are byte offsets in the supplied file. For a ROM image they are
ROM file offsets, not CPU addresses.

## Prerequisites

- Python 3.
- A ROM or binary dump readable by the current user.
- A terminal wide enough for the selected tile count and column count.

No image or audio libraries are required.

## Syntax

```sh
tools/workbench/msx/gfxview.py FILE OFFSET \
  [--count N] [--size {8,16}] [--cols C] [--bpp {1,4}]

tools/workbench/msx/gfxview.py FILE OFFSET --raw \
  [--bpp {1,4}] [--width W] [--rows R]
```

Arguments and defaults:

- `FILE` is the binary input path.
- `OFFSET` is parsed with Python base autodetection. Use `0x8000` for
  hexadecimal or `32768` for decimal. A bare `8000` means decimal.
- `--count N` renders at most `N` patterns. Default: `16`.
- `--size {8,16}` selects 8×8 or 16×16 patterns. Default: `8`.
- `--cols C` places at most `C` patterns beside each other. Default: `8`.
- `--bpp {1,4}` selects one-bit or four-bit pixels. Default: `1`.
- `--raw` treats the region as consecutive bitmap rows instead of patterns.
  Default: off.
- `--width W` sets raw row width. Default: `64`; its exact unit depends on
  `--bpp`, as described below.
- `--rows R` renders at most `R` complete raw rows. Default: `32`.
- `-h`, `--help` prints command help.

`--count`, `--size`, and `--cols` have no effect in raw mode.

## Inspect tiled 1bpp data

```sh
tools/workbench/msx/gfxview.py cart.rom 0x12000 \
  --bpp 1 --size 8 --count 32 --cols 8
```

One-bit output uses `#` for a set bit and `.` for a clear bit. Bits are drawn
most-significant first.

- An 8×8 pattern consumes 8 bytes, one byte per row.
- A 16×16 hardware sprite consumes 32 bytes in MSX quadrant order:
  top-left, bottom-left, top-right, bottom-right.

Each group starts with the input file offset of every pattern, followed by its
rows. The offset labels are hexadecimal.

## Inspect tiled 4bpp data

```sh
tools/workbench/msx/gfxview.py cart.rom 0x18000 \
  --bpp 4 --size 16 --count 8 --cols 4
```

Four-bit output uses `1` through `F` for color indices and `.` for index zero.
The high nibble is the left pixel. An N×N pattern consumes `N * N / 2` bytes
stored as linear rows; there is no quadrant rearrangement.

## Inspect a raw bitmap

For a 64-pixel-wide 4bpp region:

```sh
tools/workbench/msx/gfxview.py screen.bin 0 \
  --raw --bpp 4 --width 64 --rows 32
```

In 4bpp raw mode, `--width` is pixels and each row consumes `width / 2`
bytes. Use an even width.

In 1bpp raw mode, the implementation treats `--width` as bytes per row, not
pixels. Therefore `--width 32` consumes 32 bytes and prints 256 pixels:

```sh
tools/workbench/msx/gfxview.py patterns.bin 0 \
  --raw --bpp 1 --width 32 --rows 16
```

This unit difference is intentional documentation of current command behavior.

## Output limits and gotchas

- Rendering stops quietly at end of file. An offset beyond EOF produces no
  pattern rows; a partial final pattern or raw row is omitted.
- Negative counts, rows, or column counts produce no output. `--cols 0`
  raises an error because zero is not a valid grouping step.
- Odd 4bpp raw widths are rounded down when converted to bytes, so the output
  is one pixel narrower than requested. Prefer even widths.
- Tiled mode always advances by a complete pattern. It does not search for
  alignment or detect the correct format.
- ASCII output shows color indices, not an in-game palette.
- For mapper banks, convert a CPU address to the corresponding ROM file offset
  before launching the helper.

## Related helpers and skills

- `konami/rledec.py` can unpack Konami VRAM RLE directly into a file suitable
  for `gfxview.py`.
- `msx/pngwrite.py` supports game-specific PNG dumpers.
- Skills: `msx-gfx` for inspection and `msx-gfx-sheets` for labelled contact
  sheets.
