# `regen-bank.sh`

Disassemble one 8 KiB ROM bank with z80dasm, using a bank-specific symbol
file, and produce clean scratch assembly to fold into committed source. Use it
after the cart's mapper and CPU origin for that bank are known.

Run it from a game repository, or set `GAME` to the game root. The script
changes to that root before resolving project-relative inputs and outputs.

## Prerequisites

- Bash, Python 3, z80dasm on `PATH`, and the macOS/BSD form of `sed`.
- A game repository with `workbench.cfg`.
- A built ROM at the configured `rom` path, or selected with `ROM=`.
- `tools/sjasmplus`, the configured master assembly, source directory, and
  symbol file required by `bank_sym.py`.
- A correct `bank_org` entry unless an origin is supplied explicitly.
- An optional z80dasm block file when code/data boundaries are known.

Install the expected sjasmplus build with
`tools/workbench/bin/install-sjasmplus`. z80dasm is a separate prerequisite.

## Syntax

```sh
tools/workbench/msx/regen-bank.sh BANK [ORIGIN] [BLOCKFILE]
```

Arguments:

- `BANK` is the zero-based decimal bank number. It is used both by Python's
  decimal integer parser and by `printf`; do not pass `0x` notation.
- `ORIGIN` is the CPU address passed to z80dasm with `-g`. Default: that
  bank's `bank_org` value from `workbench.cfg`, formatted as `0xNNNN`.
- `BLOCKFILE` is passed to z80dasm with `-b`. Default: no block file.
  Relative paths are resolved from the game root.

At least `BANK` is required. Extra arguments beyond these three are currently
ignored rather than rejected.

The script also uses `bank_size`, `bank_prefix`, `rom`, and `master` from
configuration.

## Regenerate one bank

Using the configured CPU origin:

```sh
tools/workbench/msx/regen-bank.sh 7
```

Overriding the origin and supplying a window block map:

```sh
tools/workbench/msx/regen-bank.sh 7 0xA000 banks/banks_789.blocks
```

The command performs these user-visible tasks:

1. Selects bytes at `BANK * bank_size` from the assembled ROM.
2. Runs `bank_sym.py BANK`, writing the per-bank z80dasm symbols.
3. Runs z80dasm with address, labels, listing comments, origin, and symbols;
   if supplied, it also applies the block file.
4. Replaces z80dasm's `org` line with a comment because the committed master
   sets the origin with `PHASE`.
5. Copies the raw listing and cleans the copy with `strip-listing.py`.

## Outputs

With `bank_prefix = bank` and bank 7:

```text
generated/bank07.z80dasm.sym
generated/bank07.raw.asm
generated/bank07.generated.asm
```

- `bank07.generated.asm` has z80dasm byte-listing tails removed. Fold selected
  content from this file into the correct bank or window source.
- `bank07.raw.asm` retains addresses and bytes for temporary reference,
  including useful `illegal sequence` markers.
- The symbol file is generated input for z80dasm.

All three are scratch outputs. Do not replace annotated source wholesale and
do not commit generated listing tails. After folding, run `make verify`.
On success, the command prints the symbol-file destination followed by a
summary naming the clean and raw assembly outputs.

## Errors and gotchas

- `no ROM at ...` means the configured or `ROM=` image does not exist. Run
  `make`, or set `ROM=/path/to/cart.rom`.
- z80dasm must be discoverable on `PATH`; the workbench does not install it.
- The script uses `sed -i ''`, the macOS/BSD in-place syntax. It fails under
  standard GNU `sed` unless the script is adapted or BSD-compatible `sed` is
  provided.
- The temporary bank file is not protected by a shell cleanup trap. A failure
  before the explicit removal can leave a system temporary file.
- ROM length is not validated before disassembly. A bank beyond a short ROM
  yields a short slice and may fail later or produce incomplete output.
- `bank_sym.py` may reuse an existing `generated/all.sym`. Rebuild stale
  assembly symbols after label changes; see its dedicated documentation.
- A wrong CPU origin produces plausible but incorrect labels and relative
  targets. Confirm paging helpers before folding the output.
- z80dasm block maps affect rendering, not truth. Review boundaries and inspect
  the raw listing for illegal sequences.
- Existing generated files with the same stem are overwritten.

## Related helpers and skills

- `bank_sym.py` creates the per-bank symbol map.
- `strip-listing.py` creates the clean generated copy.
- `split-rom.sh` manages scaffold leftover bank binaries.
- `romscan.py` verifies references and dispatch tables before naming code.
- Skills: `msx-regen`, `msx-code-data`, `konami-msx-disasm`.
