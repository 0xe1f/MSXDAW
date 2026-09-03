# `scaffold`

Create the initial repository structure for a byte-exact MSXDAW
disassembly.

## When to use it

Use this once, after probing a ROM, to start a game repository with the
workbench submodule, bank placeholders, build configuration, verification CI,
licensing files, and project-local agent skills. It is not a generic template
updater for an established project: many destination files are overwritten.

## Prerequisites

- Run [`probe`](probe.md) first and choose the mapper and number of complete
  8 KiB banks from the evidence.
- Bash, Git, Python 3, `shasum`, and standard Unix utilities.
- The current implementation uses the macOS/BSD form `sed -i ''`; it is
  directly portable on macOS but needs adjustment before use on GNU/Linux.
- Access to the selected workbench Git URL unless
  `<destination>/tools/workbench` already exists.
- A writable existing ancestor of the destination path.

## Syntax

```sh
bin/scaffold DEST \
  [--name NAME] \
  [--mapper MAPPER] \
  [--banks N] \
  [--rom FILE] \
  [--url GIT_URL]
```

When invoking the vendored copy, use
`tools/workbench/bin/scaffold`. `DEST` is required; it may be relative or
absolute. Options can appear before or after it.

Arguments and defaults:

- `DEST`: directory to create or populate. The helper creates it and
  initializes Git if `DEST/.git` is not a directory.
- `--name NAME`: project and output stem used for `NAME.asm`, `NAME.rom`,
  `NAME.sha1`, configuration, and generated text. Default: the basename of the
  destination.
- `--mapper MAPPER`: value written to `workbench.cfg`. If omitted, the default
  is `linear` for four or fewer banks and `konami4` otherwise. Intended values
  are `linear`, `konami-scc`, `konami4`, `ascii8`, and `ascii16`; the helper
  does not validate the string.
- `--banks N`: number of 8 KiB banks. If omitted and `--rom` names an existing
  file, the default is `floor(file_size / 8192)`, with a minimum of 1.
  Otherwise the default is 16.
- `--rom FILE`: copy a ROM dump into the destination, hash it, and split it
  into initial bank binaries. There is no default ROM.
- `--url GIT_URL`: URL used only for the `tools/workbench` submodule. If
  omitted and a standalone workbench checkout and `DEST` share a parent
  directory, the URL is `../<workbench-directory>`. Otherwise it is
  `git@github.com:0xe1f/MSXDAW.git`.

There are no short options and no `--help` option. An unknown option exits
with status 2. A missing destination prints the full usage line and exits with
status 2. Always supply a value after each option; a missing value currently
ends with a Bash “unbound variable” error.

## Examples

Scaffold a 32 KiB linear cart from a probe-confirmed dump:

```sh
./bin/scaffold /work/example-cart \
  --name ExampleCart \
  --mapper linear \
  --banks 4 \
  --rom /dumps/ExampleCart.rom \
  --url git@github.com:0xe1f/MSXDAW.git
```

Allow ROM size to determine the bank count while keeping the mapper decision
explicit:

```sh
./bin/scaffold /work/example-megarom \
  --name ExampleMegaRom \
  --mapper ascii8 \
  --rom /dumps/ExampleMegaRom.rom
```

Create a ROM-less skeleton with explicit safe values:

```sh
./bin/scaffold /work/example-cart \
  --name ExampleCart \
  --mapper konami4 \
  --banks 16
```

Explicit mapper and bank values are preferred even when they equal defaults:
they record that the probe result was considered.

## Outputs and effects

The helper creates or updates these project-level artifacts:

- A Git repository and `tools/workbench` submodule, unless each already
  exists.
- `workbench.cfg` with 8 KiB bank size, bank source naming, the first four
  scan banks, and an initial repeating `4000,6000,8000,A000` CPU-origin
  schedule.
- `NAME.asm`, containing one phased 8 KiB region per bank.
- `banks/bios.inc`, `banks/ram.inc`, and an empty `banks/msx.sym`.
- `Makefile`, `.gitignore`, `AGENTS.md`, `LICENSE` when available, and
  `NOTICE`.
- `.github/workflows/verify.yml`.
- `README.md`, `docs/progress.md`, and `docs/game-notes.md`.
- `.agents/skills/.gitkeep`, `generated/`, and project-local links to all
  workbench skills.

When `--rom FILE` points to a regular file, the helper also:

- Copies it to `NAME.rom`.
- Writes its SHA-1 to `NAME.sha1`.
- Extracts `banks/bank00.bin` through the configured bank count.
- Makes each region in `NAME.asm` `INCBIN` its corresponding bank file.

In a clean destination without a usable ROM, no hash or bank binaries are
created. The master instead fills each bank with `ds 8192, 0` and comments
where the future `INCBIN` belongs. In an existing destination, old hashes and
bank binaries are not removed, and any matching old bank binary is still
included.

If the destination already has a GitHub `origin`, the generated README includes
verify and coverage badges derived from that remote. `--url` does not set or
change the game's `origin`; it only chooses the workbench submodule URL.

The final action runs [`install-skills`](install-skills.md). Success prints:

```text
scaffolded /absolute/destination (ExampleCart, mapper=linear)
```

The helper does not install sjasmplus, run the probe, run `make verify`, add
files to Git, or create a commit.

## Errors and gotchas

- An existing destination is populated in place. Configuration, source,
  templates, docs, and metadata named above may be replaced, while unrelated
  files remain. Use a new directory or review backups first.
- An existing `tools/workbench` path suppresses `git submodule add` without
  checking that the path is a valid workbench checkout.
- A nonexistent `--rom` path is silently treated like no ROM. Verify that
  `NAME.sha1` and bank binaries were created.
- ROM size is not validated for an exact 8 KiB multiple. Automatic bank count
  truncates the remainder; an explicit count larger than the dump can produce
  short or empty final bank files.
- `--banks` is used in shell arithmetic and must be a positive decimal
  integer. Zero and negative values produce unusable scaffolds; nonnumeric
  values fail during generation.
- The initial repeating CPU origins are placeholders for mapped carts. Confirm
  the paging schedule before creating window files. Linear 16/32 KiB carts have
  no pager.
- Use a shell- and filename-safe `NAME`, preferably PascalCase letters and
  digits. The value is inserted into shell-generated files and a `sed`
  replacement without escaping.
- The default workbench URL uses GitHub SSH. If SSH credentials are unavailable,
  pass an HTTPS URL with `--url`.
- If local-file submodules are blocked by Git policy, the sibling-checkout
  default may fail. Supply a network URL rather than changing global Git
  configuration.
- If the ROM already occupies exactly the destination `NAME.rom` path, the
  copy can fail because source and destination are the same file.
- Review the generated copyright line in `NOTICE` and replace it with accurate
  project attribution before publishing.

## Next tasks

1. Run `tools/workbench/bin/probe` from the new game root to create
   `docs/probe.md`.
2. Review `workbench.cfg`, especially `mapper`, `banks`, and `bank_org`.
3. Run [`install-sjasmplus`](install-sjasmplus.md).
4. Run `make verify` while the scaffold still uses byte-exact `INCBIN`s.
5. Follow `msx-bootstrap`: regenerate bank 0, name startup and paging behavior,
   verify again, and stop before inventing bank-window groupings.

The `msx-scaffold`, `msx-bootstrap`, and `msx-code-data` skills describe that
sequence in increasing depth.
