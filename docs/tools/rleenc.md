# `rleenc.py` — pack a flat buffer as Konami VRAM RLE

Use `konami/rleenc.py` to encode a contiguous flat graphics buffer in Konami's
MSX VRAM RLE grammar. It is the practical inverse of
[`rledec.py`](rledec.md) for one continuous output region.

The encoder emits:

- `01` through `7F`, followed by one byte — a run of 1 through 127 copies;
- `81` through `FF`, followed by 1 through 127 bytes — a literal block;
- `00` — end of stream.

It does not emit `80 lo hi` VRAM-address commands. Supply the destination to
the game's loader separately, or preserve address-changing source streams by
another workflow.

The encoder minimizes packed size. When equally short encodings exist, it
prefers a run and then the longer segment. This often reproduces an original
stream byte-for-byte, but byte identity is not guaranteed.

## Prerequisites

- Python 3; no third-party packages are required.
- A flat binary buffer containing exactly the contiguous bytes to encode.
- For comparison mode, the original ROM and the stream's ROM file offset.

WAV, PNG, and assembler files are not accepted directly. Extract or generate a
flat binary first.

## Syntax

```text
tools/workbench/konami/rleenc.py FLAT
    [--out FILE]
    [--verify ROM SRC]
```

## Arguments and options

- `FLAT` — input flat binary buffer. Required.
- `--out FILE` — write the encoded stream to this path. Default: no packed
  file is written; the command still encodes and checks its own round trip.
- `--verify ROM SRC` — compare the newly packed bytes with one original stream.
  `ROM` is the input ROM image and `SRC` is the original stream's ROM file
  offset. `SRC` uses Python's base-aware integer syntax; use `0x` for
  hexadecimal.
- `-h`, `--help` — print command help and exit.

The `--verify` option takes exactly two values. It may be combined with
`--out`.

## Examples

Encode a flat buffer and report its packed size:

```sh
tools/workbench/konami/rleenc.py /tmp/patterns.bin
```

Write the packed result:

```sh
tools/workbench/konami/rleenc.py /tmp/patterns.bin \
  --out /tmp/patterns.rle
```

Compare the chosen encoding with an original stream:

```sh
tools/workbench/konami/rleenc.py /tmp/patterns.bin \
  --verify Cart.rom 0x12340 --out /tmp/patterns.rle
```

## Output and verification behavior

Every run prints the flat and packed byte counts followed by
`(round-trip OK)`. The packed count includes the final `00`. The helper always
decodes its newly encoded stream and asserts that it exactly reconstructs
`FLAT`.

With `--verify`, it decodes the original stream far enough to find its ending
offset, extracts the original packed bytes including the terminator, and
reports either:

- `IDENTICAL` — the newly encoded bytes exactly match the original; or
- `differs (same pixels)` — the byte encoding is different.

Important: the second message does **not** compare the original stream's
decoded bytes with `FLAT`; it assumes the caller supplied the corresponding
pixels. Use [`rledec.py`](rledec.md) and a binary comparison when pixel equality
with the ROM must be proven.

With `--out`, the command writes the packed stream and prints its path.

## Errors and gotchas

- A bare `SRC` such as `12340` is decimal, not hexadecimal. Write `0x12340`.
- `--verify` needs both `ROM` and `SRC` on the same invocation.
- A wrong verification offset may stop at an incidental zero or read beyond
  the ROM with an `IndexError`.
- The comparison decoder skips `80 lo hi` commands and concatenates their data.
  The encoder cannot recreate those address changes, so sparse or relocated
  streams are not candidates for a byte-exact round trip.
- `differs (same pixels)` guarantees neither original-pixel equality nor
  suitability as an in-place ROM replacement. Check the decoded buffers and
  available packed space yourself.
- The encoded result may be smaller than the original while still differing
  byte-for-byte. Keep untouched original bytes authoritative when pursuing a
  byte-exact disassembly.
- `--out` does not create missing parent directories. Create them first.
- An empty input is valid and encodes as the one-byte terminator `00`.

## Related helpers and skills

- [`rledec.py`](rledec.md) — decode a ROM stream and recover its VRAM span.
- `msx/gfxview.py` — inspect flat 1bpp or 4bpp graphics before repacking.
- `msx/pngwrite.py` — library used by cart-specific PNG workflows.
- `msx-gfx` — graphics inspection and Konami RLE workflow.
- `msx-gfx-sheets` — conventions for labelled cart-specific graphics
  catalogues; generated previews do not replace authoritative assembly bytes.
