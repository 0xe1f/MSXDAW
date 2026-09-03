# `probe`

Produce a first-pass, cart-neutral identification report for an MSX ROM.

## When to use it

Probe a dump before choosing scaffold mapper and bank-count values. Re-run it
from a newly scaffolded game to save the baseline report as
`docs/probe.md`. The report is evidence for initial setup, not a substitute for
tracing the cart's paging behavior.

## Prerequisites

- Python 3.
- A readable ROM dump.
- For argument-free use, a game repository discoverable through
  `workbench.cfg`.

The helper does not require third-party Python packages.

## Syntax

```sh
tools/workbench/bin/probe [ROM] [-o PATH]
```

Arguments and options:

- `ROM`: optional ROM path. With no ROM argument, the helper finds the nearest
  game root by walking upward from the current directory (or by using `GAME`)
  and reads the ROM configured by `workbench.cfg`. The `ROM` environment
  variable overrides that configured ROM path.
- `-o PATH`, `--out PATH`: write Markdown to `PATH`, creating parent
  directories as needed.
- `-h`, `--help`: show argparse help and exit.

Output defaults depend on how the ROM was selected:

- No `ROM` argument: write `<game-root>/docs/probe.md`.
- Explicit `ROM` argument: print the report to standard output, even when
  launched inside a game repository.
- `-o` always selects the output file in either mode. A relative path is
  resolved from the current directory.

## Examples

Inspect a dump before a project exists:

```sh
tools/workbench/bin/probe /dumps/ExampleCart.rom
```

Save that report explicitly:

```sh
tools/workbench/bin/probe /dumps/ExampleCart.rom \
  --out /work/example-cart/docs/probe.md
```

After scaffolding, run from the game root and use `workbench.cfg`:

```sh
tools/workbench/bin/probe
```

Use a temporary ROM without changing `workbench.cfg`:

```sh
ROM=/dumps/clean.rom tools/workbench/bin/probe
```

## Report contents

The Markdown report includes:

- ROM path, byte and KiB size, SHA-1, and the count of complete 8 KiB banks.
- Whether file offset 0 starts with the MSX `AB` header and, when present, its
  init address.
- The three bytes at file offset `0x3FFD`, when the ROM is at least 16 KiB, as
  a possible Konami page-ending stamp.
- Counts of literal `ld (nn),a` byte sequences at known Konami, SCC, ASCII8,
  and ASCII16 mapper-select addresses.
- A mapper guess: `linear`, `konami4`, `konami-scc`, `ascii8`, `ascii16`, or
  `unknown`.
- Whether the exact contiguous SCC-enable sequence
  `ld a,3Fh / ld (9000h),a` occurs, with its file offset when found.

A file output is replaced, not appended. Success prints `wrote PATH`; standard
output mode emits only the Markdown report.

## Errors and gotchas

- `ROM path required (no workbench.cfg in cwd)` means argument-free mode could
  not find a game configuration. Pass the ROM explicitly, change into the game
  tree, or set `GAME` to the game root or its `workbench.cfg`.
- `no ROM at ...` means the selected path is not a regular file. Check
  `workbench.cfg`, `ROM`, and the current directory used for relative paths.
- Mapper detection is heuristic. It counts matching bytes anywhere in the ROM,
  including data, and can report false positives. Confirm paging helpers before
  creating bank-window source files.
- The 8 KiB bank count uses integer division. A truncated or non-bank-aligned
  dump is still reported; inspect the byte size before passing a count to
  `scaffold`.
- The SCC check recognizes only one exact five-byte encoding. “Not found” does
  not prove the cart lacks SCC support.
- An `AB` header is checked only at file offset 0.
- The helper writes a report only. It does not alter the ROM, scaffold a
  project, add files to Git, or commit anything.

## Related helpers and skills

- [`scaffold`](scaffold.md) consumes the mapper and bank-count decisions made
  from this report.
- `msx-scaffold` explains how to interpret the initial mapper evidence.
- `msx-bootstrap` continues with bank 0, the `AB` header, startup, interrupt
  hooks, and paging helpers.
- `msx-romscan` performs deeper static cross-reference and dispatch-table
  analysis after the project exists.
