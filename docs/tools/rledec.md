# `rledec.py` — unpack Konami VRAM RLE

Use `konami/rledec.py` to decompress one Konami MSX graphics RLE stream from a
ROM into a flat binary image. The result can be inspected directly with
`msx/gfxview.py` or used as the input to an asset-editing workflow.

The supported stream grammar is:

- `00` — end of stream;
- `80 lo hi` — set the VRAM write pointer to `hi << 8 | lo`;
- `01` through `7F` — repeat the following byte 1 through 127 times;
- `81` through `FF` — copy the following 1 through 127 bytes literally.

## Prerequisites

- Python 3; no third-party packages are required.
- A ROM or binary file containing a complete stream.
- The stream's **ROM file offset**.
- The initial VRAM destination used by the game's loader, if it differs from
  the default `0xF800`.

The source offset is not a bank-relative or CPU address. Convert a CPU address
to its ROM file offset before invoking this helper.

## Syntax

```text
tools/workbench/konami/rledec.py ROMFILE OFFSET
    [--dest VRAM_ADDRESS] [--out FILE]
```

## Arguments and options

- `ROMFILE` — input ROM or binary image. Required.
- `OFFSET` — source file offset of the first RLE control byte. Required.
  Parsed with Python's base-aware integer syntax: use `0x` for hexadecimal.
- `--dest VRAM_ADDRESS` — initial VRAM write address. Default: `0xF800`.
  The value is parsed with the same base-aware syntax.
- `--out FILE` — write the flattened decompressed bytes to this path.
  Default: no file is written; only the source and destination summaries are
  printed.
- `-h`, `--help` — print command help and exit.

There are no options for input length or output size. Decoding continues until
the first `00` terminator.

## Examples

Inspect a stream's extents without writing a file:

```sh
tools/workbench/konami/rledec.py Cart.rom 0x12340 --dest 0x3800
```

Write a flat graphics buffer:

```sh
tools/workbench/konami/rledec.py Cart.rom 0x12340 \
  --dest 0x3800 --out /tmp/patterns.bin
```

View the result as sixteen 16×16, 1bpp sprite patterns:

```sh
tools/workbench/msx/gfxview.py /tmp/patterns.bin 0 \
  --bpp 1 --size 16 --count 16 --cols 8
```

## Output and address behavior

The command always prints:

- the source start, parser end, and compressed byte count;
- the lowest and highest VRAM addresses represented in the flat output, plus
  its byte count.

With `--out`, it then writes the binary and prints its path. The compressed
byte count includes the terminating `00` and any `80 lo hi` address-change
commands.

The output spans from the lowest through the highest VRAM address written.
Address changes may write out of order. Any unwritten holes between those
addresses become zero bytes in the flat file, so output offset zero corresponds
to the printed lowest VRAM address, not necessarily the `--dest` value.

## Errors and gotchas

- A bare value such as `12340` is decimal, not hexadecimal. Write `0x12340`.
- If `OFFSET` is wrong, the decoder may stop early at an incidental zero, run
  beyond the input with an `IndexError`, or produce an implausibly large VRAM
  span. Recheck the ROM file offset and stream grammar.
- A stream that terminates without writing any bytes fails when the tool tries
  to determine its minimum and maximum VRAM addresses.
- `--dest` matters until the stream issues `80 lo hi`. Use the destination
  loaded by the game, especially for streams without an address command.
- `--out` does not create missing parent directories. Create them first.
- The printed source range uses the parser's end position after the terminator;
  use the compressed byte count when identifying the exact source extent.
- The flat output does not preserve address-change commands or sparse layout.
  Keep the original packed bytes authoritative in a byte-exact disassembly.

## Related helpers and skills

- [`rleenc.py`](rleenc.md) — encode a contiguous flat buffer back into this RLE
  grammar.
- `msx/gfxview.py` — inspect decompressed 1bpp or 4bpp graphics.
- `msx/pngwrite.py` — library used by cart-specific PNG dumpers.
- `msx-gfx` — identify graphics layouts and use the RLE helpers.
- `msx-gfx-sheets` — build labelled, cart-specific PNG catalogues after the
  data and palette are understood.
