# `install-sjasmplus`

Build the sjasmplus version used by MSXDAW and install the executable in one
game repository.

## When to use it

Run this after scaffolding a game, when `make` reports that
`tools/sjasmplus` is missing, or when the pinned assembler must be rebuilt.
The installed executable is local to the game and is normally gitignored.

## Prerequisites

- Run from a game repository, or one of its descendants, where
  `workbench.cfg` is present. Calling the vendored
  `tools/workbench/bin/install-sjasmplus` also finds that game root.
- `git`, `make`, and a C++ compiler available as `c++`.
- Network access to clone `https://github.com/z00m128/sjasmplus.git`.
- Permission to create a temporary directory and write `tools/sjasmplus`.

## Syntax

```sh
tools/workbench/bin/install-sjasmplus [--force]
```

Options:

- `--force`, `-f`: build and replace `tools/sjasmplus` even when an executable
  already exists there. The default is to keep an existing executable.

There are no positional arguments. Any other option or argument prints
`usage: install-sjasmplus [--force]` and exits with status 2.

The source tag defaults to `v1.24.0`, matching the scaffolded verify workflow.
For controlled testing, `SJASMPLUS_TAG` overrides the Git tag or branch:

```sh
SJASMPLUS_TAG=v1.24.0 tools/workbench/bin/install-sjasmplus --force
```

Use an override deliberately: a different assembler can make local output
disagree with CI.

## Examples

Install the pinned assembler from the game root:

```sh
tools/workbench/bin/install-sjasmplus
```

Rebuild a damaged or stale executable:

```sh
tools/workbench/bin/install-sjasmplus --force
make verify
```

## Outputs and effects

The helper recursively clones the selected sjasmplus tag into a temporary
directory, runs its build, and copies the resulting executable to:

```text
<game-root>/tools/sjasmplus
```

The temporary clone is removed on exit. A successful installation prints the
destination and the first line of `sjasmplus --version`.

If an executable already exists and `--force` is absent, no clone or build is
performed. The helper prints `already installed: ...` with its version and
exits successfully. A non-executable file at that path does not count as an
installation and will be replaced after a successful build.

## Errors and gotchas

- `install-sjasmplus: run from a game repo (workbench.cfg)` means no game root
  could be found. Change into the game tree or call its vendored helper.
- `install-sjasmplus: need git, make, and a C++ compiler` names the required
  commands. On macOS, installing the Command Line Tools normally supplies the
  compiler and build tools.
- Clone errors commonly mean the selected `SJASMPLUS_TAG` does not exist,
  network access failed, or Git could not fetch submodules.
- Build failures leave the existing destination untouched; the temporary build
  tree is removed.
- Without `--force`, any executable at the destination is accepted regardless
  of version. Read the reported version and force a rebuild if it differs from
  the CI pin.
- The helper installs only the assembler. It does not run `make verify`, add
  files to Git, or commit anything.

## Related helpers and skills

- [`scaffold`](scaffold.md) creates the game project but does not install the
  assembler.
- The `msx-scaffold` skill defines the supported setup sequence and CI pin.
- After installation, use the scaffolded `make verify` target to assemble and
  compare the result with the committed SHA-1.
