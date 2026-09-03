# `bank_sym.py`

Build a z80dasm symbol file for one 8 KiB bank, or audit labels that occupy
the same CPU address in different banks. Use it before regenerating a bank
with `regen-bank.sh`, and after changing labels that z80dasm should use.

Run it from a game repository, or set `GAME` to the game root. The helper
walks upward for `workbench.cfg`.

## Prerequisites

- Python 3.
- A game repository with `workbench.cfg`.
- The configured master assembly and source directory.
- `tools/sjasmplus`, when `generated/all.sym` must be built or when auditing.
- The configured `sym` file, normally `banks/msx.sym`, if shared BIOS and
  cross-bank names should be available. A missing file is treated as empty.

The relevant configuration keys are `master`, `source_dir`, `sym`, `banks`,
`bank_size`, `bank_prefix`, and `bank_org`.

## Syntax

```sh
tools/workbench/msx/bank_sym.py BANK [--stdout]
tools/workbench/msx/bank_sym.py --audit
```

`BANK` is a zero-based decimal bank number. It must be in the configured
range `0` through `banks - 1`; hexadecimal notation is not accepted.

Options:

- `--stdout` prints the generated symbol file instead of writing it.
- `--audit` assembles a fresh listing and prints cross-bank CPU-address
  collisions. It does not write a per-bank symbol file.
- `-h`, `--help` prints command help.

If `--audit` is present, it takes precedence over `BANK` and `--stdout`.
Without either a bank or `--audit`, the command exits with an argument error.

## Generate symbols for a bank

```sh
tools/workbench/msx/bank_sym.py 6
```

The command writes:

```text
generated/<bank_prefix>06.z80dasm.sym
```

With the conventional prefix, that is
`generated/bank06.z80dasm.sym`. The file contains at most one symbol per CPU
address:

- BIOS names below `0x4000`;
- unambiguous `msx.sym` names outside this bank's CPU window; and
- non-auto labels defined in this bank's configured window.

Addresses at or above `0xC000` are excluded. z80dasm-style names such as
`l8123h` and `sub_8123h` are deliberately omitted so z80dasm can create them.
The output is generated scratch and should not be edited or committed.
A successful write also prints the destination path.

To inspect the same content without changing the filesystem:

```sh
tools/workbench/msx/bank_sym.py 6 --stdout
```

## Audit overlapping bank labels

```sh
tools/workbench/msx/bank_sym.py --audit
```

The audit rebuilds `generated/all.sym` and
`generated/<game-name>.lst`, then reports CPU addresses with labels in more
than one bank. Its summary distinguishes named-vs-named from named-vs-auto
collisions; the detailed section lists named-vs-named collisions.

Overlapping CPU windows are normal in a banked cart. A collision means a flat
z80dasm symbol map cannot represent both names at once; it does not by itself
mean either label is wrong. Window files that reuse a CPU range normally need
sjasmplus `MODULE` scoping.

## Errors and gotchas

- A normal bank run reuses `generated/all.sym` if it already exists. It does
  not check whether that file is stale. Remove or rebuild it after source
  label changes, or run `--audit` first to force a fresh assembly.
- Assembly failures propagate from `tools/sjasmplus`. Confirm the master
  assembles and that the executable exists.
- `bank_org` must describe the cart's real paging behavior. A wrong origin
  filters the wrong labels into the bank file.
- `msx.sym` is flat. Multiple names at the same non-BIOS address are omitted
  unless a real source label in the selected bank resolves the ambiguity.
- Set `GAME=/path/to/cart` when invoking the helper outside the game tree;
  otherwise `no workbench.cfg found` is fatal.

## Related helpers and skills

- `regen-bank.sh` consumes the generated per-bank symbol file.
- `strip-listing.py` cleans regenerated z80dasm output.
- `romscan.py` finds ROM references without relying on a flat symbol map.
- Skills: `msx-regen`, `konami-msx-disasm`.
