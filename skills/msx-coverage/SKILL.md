---
name: msx-coverage
description: >-
  Disassembly progress badges and coverage.py (INCBIN leftover, auto
  labels, opcode comments, annotated call targets). Use when adding
  Shields.io coverage badges, the CI coverage job, asking how
  disassembled the cart is, or running make coverage. Not test coverage.
---

# Disassembly coverage

How far the cart has left the scaffold. Not test coverage. Not a single
percent. Run from the **game** repo root (`workbench.cfg`).

```
make coverage
tools/workbench/msx/coverage.py
tools/workbench/msx/coverage.py --badges generated/badges
```

`make coverage` writes Shields.io endpoint JSON under `generated/badges/`
(gitignored) and prints the report. It does **not** edit `README.md`.

## README (static URLs)

Do not rewrite README on each commit. After the verify badge, add endpoint
badges. Infer `owner/repo` from `git remote get-url origin`. Do not invent
a slug.

```
[![in source](https://img.shields.io/endpoint?style=flat&url=https://raw.githubusercontent.com/owner/repo/badges/in-source.json)](https://github.com/owner/repo/actions/workflows/verify.yml)
[![named](https://img.shields.io/endpoint?style=flat&url=https://raw.githubusercontent.com/owner/repo/badges/named.json)](https://github.com/owner/repo/actions/workflows/verify.yml)
[![op comments](https://img.shields.io/endpoint?style=flat&url=https://raw.githubusercontent.com/owner/repo/badges/op-comments.json)](https://github.com/owner/repo/actions/workflows/verify.yml)
[![sub comments](https://img.shields.io/endpoint?style=flat&url=https://raw.githubusercontent.com/owner/repo/badges/sub-comments.json)](https://github.com/owner/repo/actions/workflows/verify.yml)
```

CI (`msx-scaffold` workflow) sparse-clones workbench `msx/` + `lib/`, runs
`--badges`, and force-pushes an orphan `badges` branch on the default
branch only. Pull requests get the report in the job summary, not a push.
Until the first default-branch run, Shields may show “invalid”.

`--readme` exists for offline trees with no GitHub. Do not use it when
endpoint badges are in place.

## Layers

| Badge | Count | Done when |
|---|---|---|
| **in source** | ROM bytes not behind `INCBIN` / leftover `.bin` | every ROM byte is `.asm` |
| **named** | unique remaining `lXXXXh` / `sub_XXXXh` **definitions** (countdown) | no z80dasm auto labels |
| **op comments** | instruction lines with a `;` comment | long tail; not a merge gate |
| **sub comments** | named `call` targets with a comment block immediately above | every called routine has docs |

A counted sub is a named label that is a `call` target and whose next real
line is an opcode (`lXXXXh` / BIOS `equ` / tables do not count). **+1** if
the lines above it (skipping blanks and `====` rules) include a `;` comment
with a letter; **+0** otherwise. A trailing `;` on the label line is not
docs. `jp` / `jr` locals are not counted.

Do not put a single “N% disassembled” figure on the README. Do not
hero-number `msx.sym` size. `defb` / `defw` / `INCBIN` are not opcodes.
The per-window table is in the printed report / job summary / `coverage.md`
on the `badges` branch, not the README.

Verify assemble job: `msx-scaffold`.
