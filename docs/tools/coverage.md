# `coverage.py`

Report disassembly progress from committed assembly source. This is source
coverage, not test coverage: it tracks bytes still behind `INCBIN`, remaining
z80dasm auto labels, commented opcode lines, and documented named call targets.

Run it from a game repository, or set `GAME` to the game root. The helper
walks upward for `workbench.cfg`.

## Prerequisites

- Python 3.
- A game repository with `workbench.cfg`.
- The configured master assembly and source directory.
- A built ROM is optional. If present, its file size is the total byte count;
  otherwise total size is `banks * bank_size` from configuration.

The scan reads the configured master plus `.asm` and `.inc` files recursively
under `source_dir`. It skips paths containing `.git`, `generated`, `tools`,
`gfx`, `music`, `sfx`, or `__pycache__`.

## Syntax

```sh
tools/workbench/msx/coverage.py [--json] [--badges DIR] [--readme [PATH]]
```

Options:

- `--json` prints the complete statistics object instead of the text report.
  Default: off.
- `--badges DIR` writes badge endpoint files under `DIR`. A relative path is
  resolved from the game root. Default: do not write badge files.
- `--readme [PATH]` inserts or replaces a coverage block in `PATH`. If the
  option is given without a path, `README.md` is used. A relative path is
  resolved from the game root. Default: do not edit a Markdown file.
- `-h`, `--help` prints command help.

The options may be combined. `--json` only changes standard output; badge and
README writes still occur when requested.

## Print a progress report

```sh
tools/workbench/msx/coverage.py
```

The report includes four cart-wide measures:

- `In source`: labelled ROM bytes represented directly in assembly rather
  than by `INCBIN` or leftover bank `.bin` files.
- `Named`: unique definitions named `lXXXXh` or `sub_XXXXh` that remain.
- `Op comments`: opcode lines containing a semicolon.
- `Sub comments`: named `call` targets whose routine label is immediately
  preceded by a comment block containing letters.

If unfinished work can be assigned to top-level bank/window files, a Markdown
table follows for files that still contain `INCBIN`, auto labels, or
undocumented named `call` targets. Window stems are `banks_` plus hexadecimal
bank ids; conventional `bankNN` and legacy `segNN` stems are also recognized.

Use JSON for scripts:

```sh
tools/workbench/msx/coverage.py --json > generated/coverage.json
```

The object contains `rom_bytes`, `labelled_bytes`, `incbin_bytes`,
`auto_labels`, opcode and subroutine counts and percentages, plus per-window
statistics.

## Generate Shields.io endpoint files

```sh
tools/workbench/msx/coverage.py --badges generated/badges
```

This creates the directory if needed and writes:

```text
coverage.json
coverage.md
in-source.json
named.json
op-comments.json
sub-comments.json
```

The four small JSON files use the Shields endpoint schema and a cache time of
300 seconds. `coverage.json` contains raw statistics; `coverage.md` contains
the text report. The scaffolded `make coverage` target uses this mode.

## Write an offline README block

```sh
tools/workbench/msx/coverage.py --readme
tools/workbench/msx/coverage.py --readme docs/status.md
```

The command replaces content between `<!-- coverage -->` and
`<!-- /coverage -->`. If the markers are absent, it inserts the block after
the leading title and image/badge lines. If the target does not exist, it is
created.

This mode changes the selected file in place. It is intended for offline
trees; repositories using CI-published endpoint badges should keep static
badge URLs instead of rewriting README content on every run.

## Counting details and gotchas

- Repeated references to the same `INCBIN` path count its largest requested
  span once cart-wide. Unreferenced conventional leftover bank `.bin` files
  are also counted.
- `INCBIN` offsets and lengths accept decimal, `0x` hexadecimal, or a trailing
  `h`. Missing files contribute zero unless the basename is a conventional
  bank binary, in which case `bank_size` is assumed.
- The total leftover count is capped at total ROM bytes. Incorrect paths can
  therefore make coverage look better, not fail the command; investigate
  unexpected jumps.
- Any semicolon on a recognized instruction line counts as an opcode comment;
  comment quality is not evaluated.
- Only named direct `call` targets count as subroutines. Auto labels, tables,
  BIOS `equ` names, and `jp`/`jr`-only local routines do not.
- A trailing comment on the routine label is not documentation. The qualifying
  comment block must be above the label.
- Window detail is only attributed to top-level source files with recognized
  stems. Included files still affect cart-wide totals.
- Set `GAME=/path/to/cart` when running outside the game tree.

## Related helpers and skills

- `split-rom.sh` refreshes the leftover bank files included in the byte count.
- `regen-bank.sh` and `bank_sym.py` reduce scaffold and auto-label debt.
- Skills: `msx-coverage`, `msx-scaffold`, `msx-code-data`.
