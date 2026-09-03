# `split-rom.sh`

Refresh scaffold-era 8 KiB bank binaries from the ROM and remove leftover
binaries for banks that have graduated to assembly source. This is the helper
behind the scaffolded `make banks` target.

Run it from a game repository, or set `GAME` to the game root. The script
walks upward for `workbench.cfg` and changes to that root.

## Prerequisites

- Bash and Python 3.
- A game repository with `workbench.cfg`.
- For extraction, a built ROM at the configured `rom` path or selected with
  `ROM=`.

The helper uses `banks`, `bank_size`, `source_dir`, `bank_prefix`, `rom`, and
the optional `migrated` configuration value.

## Syntax

```sh
tools/workbench/msx/split-rom.sh
```

There are no supported options or arguments. Current shell behavior does not
reject extra arguments, but they have no effect.

The equivalent scaffold target is:

```sh
make banks
```

## Refresh leftover bank files

```sh
ROM=/tmp/cart.rom tools/workbench/msx/split-rom.sh
```

For every configured zero-based bank index:

- If the bank is migrated, its leftover
  `<source_dir>/<bank_prefix>NN.bin` is deleted if present.
- Otherwise, if a ROM is available, the corresponding `bank_size` byte slice
  is written to that leftover path.

The source directory is created, including missing parents. Existing leftover
files for unmigrated banks are overwritten.

A bank is considered migrated when any of these is true:

- `migrated = all` or `migrated = *` in `workbench.cfg`;
- its decimal index appears in the comma- or space-separated `migrated` list;
  or
- `<source_dir>/<bank_prefix>NN.asm` exists.

Window files do not automatically mark their component banks as migrated.
Once sources are combined into windows, configure `migrated` explicitly.

The command finishes with a summary such as:

```text
migrated 6 banks (no leftover .bin); extracted 10 leftover bins
```

## Missing-ROM behavior

If no ROM exists, the helper still creates the source directory and deletes
leftover binaries for migrated banks. It leaves unmigrated binaries unchanged.
When any unmigrated banks remain, it prints a warning:

```text
no ROM at <path> (set ROM= or run make) — leftover bins not refreshed
```

This condition exits successfully; automation must not rely on the exit code
to prove that extraction occurred.

## Errors and gotchas

- This command is destructive for migrated bank binaries and overwrites
  unmigrated bank binaries. Commit or otherwise preserve deliberate fixtures
  before running it.
- ROM size is not validated. A short image writes short or empty slices for
  later banks.
- Merely creating a conventional per-bank `.asm` file marks that bank
  migrated, regardless of whether the master includes it or whether it is
  complete.
- A combined window `.asm` has no conventional per-bank stem, so use the
  `migrated` configuration list or `all`.
- The migration list parses decimal and `0x`-prefixed values, separated by
  commas or spaces.
- Set `GAME=/path/to/cart` when invoking outside the game tree; otherwise a
  missing `workbench.cfg` is fatal.
- Leftover binaries are scaffold only. The end state remains labelled assembly
  for every ROM byte, followed by `make verify`.

## Related helpers and skills

- `regen-bank.sh` produces the first clean assembly for a selected bank.
- `coverage.py` counts remaining leftover bank files and `INCBIN` spans.
- `bank_sym.py` prepares symbols for regeneration.
- Skills: `msx-bootstrap`, `msx-regen`, `msx-code-data`.
