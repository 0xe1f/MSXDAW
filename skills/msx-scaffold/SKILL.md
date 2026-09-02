---
name: msx-scaffold
description: >-
  Create a new MSXDAW game repo from a ROM dump: probe mapper and size,
  run bin/scaffold, wire the workbench submodule, LICENSE/README/CI,
  sjasmplus, then hand off to msx-bootstrap. Use when starting a second
  cart, scaffolding a new disassembly, or the user asks for a repo like
  King's Valley II / Vampire Killer.
---

# New MSXDAW game repo

Do this **before** `msx-bootstrap`. Do not copy another game’s window files,
`bank_org`, RAM map, or Konami SCC assumptions.

## Probe first

```
tools/workbench/bin/probe /path/to/Game.rom
```

Read size, SHA-1, `AB` init, and mapper guess. Then:

| Guess | Typical size | `--mapper` | `--banks` |
|---|---|---|---|
| `linear` | 16 or 32 KiB | `linear` | `size/8192` (2 or 4) |
| `konami4` | 128 KiB+ | `konami4` | 16, 32, … |
| `konami-scc` | 128 KiB+ | `konami-scc` | 16, 32, … |
| `ascii8` / `ascii16` | MegaROM | that name | `size/8192` |

16/32 KiB is an unmapped cart (CPU `4000-7FFF` or `4000-BFFF`), not a
MegaROM. Scaffold defaults were historically `--mapper konami4 --banks 16`
— **override** from the probe. Coincidental `ld (6000h),a` on a 32 KiB dump
is not Konami4.

ASCII8 unique ports: `6800` / `7800`. Konami SCC unique: `5000` / `9000` /
`B000`. Konami4 unique: `8000` / `A000` on a cart larger than 32 KiB.

Dest directory: `~/code/<game>` (lowercase), `--name` PascalCase like
`Arkanoid` / `KingsValley2`.

## Scaffold

From any workbench checkout:

```
tools/workbench/bin/scaffold ~/code/<game> \
  --name Game \
  --mapper <probe> \
  --banks <n> \
  --rom /path/to/Game.rom \
  --url git@github.com:0xe1f/MSXDAW.git
```

`--rom` copies the dump (gitignored), writes `<Game>.sha1`, extracts leftover
8 KiB bins, and (if `--banks` omitted) sets bank count from file size.
`--mapper` omitted + 4 or fewer banks → `linear`. `--url` omitted → GitHub
unless dest is a sibling of a standalone DAW clone. **Never** submodule a
nested `kingsvalley2/tools/workbench` path.

## After scaffold (same session)

1. `docs/probe.md` — run `bin/probe` from the **new** repo root.
2. `workbench.cfg` — set `bank_org` from the mapper (`4000,6000,8000,A000`
   for linear 32 KiB; drop trailing pages for 16 KiB).
3. Install sjasmplus (gitignored `tools/sjasmplus`):
   ```
   tools/workbench/bin/install-sjasmplus
   ```
   Clones [z00m128/sjasmplus](https://github.com/z00m128/sjasmplus) **v1.24.0**
   (`--recursive`), builds, copies into this game. Idempotent if the binary
   is already there (`--force` to rebuild). Need git, make, and a C++ compiler.
   A copy/symlink from another DAW game is fine only if that binary is the
   same pin.
4. `cocoamsx.json` from `tools/workbench/cocoamsx/cocoamsx.json.example`.
   Pick `MSX - C-BIOS` vs `MSX2 - C-BIOS` from the cart generation.
5. `.github/workflows/verify.yml` — `tools/workbench/bin/install-sjasmplus`,
   `make verify`, delete the assembled ROM. Parameterize the `.rom` name.
6. `NOTICE` copyright line: original publisher + year. Apache covers
   **our** comments and structure only.
7. `bin/install-skills` (scaffold already runs it).
8. `make verify` on the `INCBIN` scaffold. Never leave it red.

Then **`msx-bootstrap`**: regen **bank 0** only, name `AB` / init / `H.TIMI`
/ pager (if any). Stop. No window files until this cart’s pager is named.
Linear carts have no pager — do not apply `konami-msx-disasm` window merge.

## Do not

- Copy `banks_123` / triplet stems from another cart.
- Commit `*.rom` or leftover `banks/*.bin`.
- Put ROM-specific addresses in a DAW skill (those go in `.agents/skills/`).
- `git commit` unless the user asks.
- Invent ASCII vs Konami from entropy or from a different game’s notes.

## Example (Taito Arkanoid, 32 KiB)

Dump: `~/emu/MSX/Carts/Other/Arkanoid.rom`. Probe should report **linear**, 4
banks, `AB` at file offset 0. Dest `~/code/arkanoid`, `--name Arkanoid`.
MSX1 + paddle (Vaus). No Konami window files. After `make verify` on INCBINs,
`msx-bootstrap` regen bank 0 only.
