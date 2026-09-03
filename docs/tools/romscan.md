# `romscan.py`

Search a banked Z80 ROM for static references to a CPU address, or decode a
byte/word dispatch table. Use it instead of grepping binaries or writing a
cart-specific one-off scanner.

Run it from a game repository, or set `GAME` to the game root. The helper
walks upward for `workbench.cfg`.

## Prerequisites

- Python 3.
- A game repository with `workbench.cfg`.
- A built ROM at the configured `rom` path, selected through `ROM=`, or passed
  explicitly with `--rom`.
- Correct `bank_size`, `banks`, `bank_org`, and `scan_banks` configuration.

## Syntax

```sh
tools/workbench/msx/romscan.py [--rom ROM] xref ADDR \
  [--banks LIST] [--base ADDR]

tools/workbench/msx/romscan.py [--rom ROM] table ADDR \
  (--words N | --bytes N) [--bank N] [--base ADDR] [--index-base N]
```

Global options must precede `xref` or `table`:

- `--rom ROM` selects a ROM image. Default: `ROM=`, then the configured `rom`
  path. Unlike configured and environment-selected paths, an explicit relative
  path is resolved from the process's current directory.
- `-h`, `--help` prints command help. A subcommand followed by `--help` prints
  help for that subcommand.

Numbers parsed as addresses or counts accept decimal or `0x`-prefixed
hexadecimal. Bare hexadecimal such as `A000` is invalid.

## Find references

```sh
tools/workbench/msx/romscan.py xref 0x8120
tools/workbench/msx/romscan.py xref 0x8120 --banks 2,3,6
tools/workbench/msx/romscan.py --rom /tmp/cart.rom \
  xref 0x8120 --banks 2,3 --base 0x8000
```

`xref` arguments and defaults:

- `ADDR` is the 16-bit CPU target to search for.
- `--banks LIST` is a comma-separated list of decimal bank indexes. Default:
  `scan_banks` from `workbench.cfg`. The deprecated alias `--segs` is accepted.
- `--base ADDR` assigns one CPU origin to every listed bank. Default: each
  bank's individual `bank_org` value.

Output marked `code` is a recognized real transfer:

- absolute `call` or unconditional/conditional `jp`; or
- `jr`/conditional `jr`/`djnz` whose displacement resolves to the target.

Output marked `data?` is a matching little-endian word not immediately
preceded by a recognized absolute transfer opcode. It may be a pointer table
entry or a coincidence and must be verified.

If no matches exist, the command prints `(no references found)`. Otherwise it
prints a total and reminds the reader that `data?` is uncertain.

## Decode a table

Decode six little-endian handler addresses:

```sh
tools/workbench/msx/romscan.py table 0x9A40 --words 6 --bank 5
```

Decode 16 byte entries whose dispatcher treats the first entry as index 1:

```sh
tools/workbench/msx/romscan.py table 0x6030 \
  --bytes 0x10 --bank 9 --index-base 1
```

`table` arguments and defaults:

- `ADDR` is the CPU address of the first table entry.
- Exactly one of `--words N` or `--bytes N` is required. Words are decoded
  little-endian; bytes are printed in hexadecimal and decimal.
- `--bank N` selects a zero-based decimal bank index. The deprecated alias
  `--seg` is accepted. If omitted, the helper selects the first bank whose
  configured origin equals `ADDR & 0xE000`; if none matches, it falls back to
  bank 0.
- `--base ADDR` overrides that bank's CPU origin. Default: its configured
  `bank_org`.
- `--index-base N` adds `N` to displayed entry indexes. Default: `0`. Use `1`
  when a dispatcher decrements a one-based selector before indexing.

The command prints a heading with table address, bank, entry count, width, and
nonzero index adjustment, followed by each decoded entry.

## Errors and gotchas

- `no ROM at ...` means the selected image is absent. Run `make`, set `ROM=`,
  or pass `--rom` before the subcommand.
- A bank whose byte range exceeds the ROM causes a fatal out-of-range error.
- `--banks` entries are decimal only even though addresses and counts accept
  `0x` notation.
- `xref` is a byte-pattern scanner, not a disassembler. It recognizes a fixed
  set of transfer opcodes and can report false positives inside data.
- Relative transfers are only checked when the target lies inside the scanned
  bank's configured CPU window.
- No `code` result does not prove an entry is unused; callers may use computed
  or stored pointers.
- Table decoding validates the starting address but not the complete requested
  span. A count that runs past the bank can end with a Python index error.
- Automatic table bank selection can be ambiguous when many banks share an
  origin. Pass `--bank` whenever the mapped bank is known.
- `--base` on `xref` applies the same origin to all selected banks.

## Related helpers and skills

- `regen-bank.sh` regenerates a bank after references and boundaries are known.
- `bank_sym.py` handles overlapping symbols for z80dasm.
- Runtime-computed references require tracing rather than static scanning.
- Skills: `msx-romscan`, `msx-code-data`, `msx-cocoamsx`.
