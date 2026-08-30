# MSXDAW — MSX Disassembly Workbench

Tools, skills, and templates for **byte-exact** Z80 disassemblies of MSX / MSX2
MegaROMs. Not a game.

Game repos (Vampire Killer, King's Valley II, …) consume this tree as the git
submodule `tools/workbench`.

## Layout

| Path | What |
|---|---|
| `msx/` | Mapper-agnostic: regen, romscan, split-rom, gfxview, pngwrite, Taito PSG (`taitoplay.py`) |
| `konami/` | Konami VRAM RLE, packed-PSG (`psgplay.py` / `sccplay.py`) |
| `lib/game.py` | Find the game root (`workbench.cfg`) |
| `bin/probe` | Mapper / `AB` / Konami stamp report |
| `bin/scaffold` | New game repo (skill `msx-scaffold`; probe first) |
| `bin/add-skill` / `bin/install-skills` | Skills + project `.cursor/skills` symlinks |
| `cocoamsx/` | Research display: CALayer present, JSON config, control socket (`tools/disasm/`, skill `msx-cocoamsx`) |
| `skills/` | Generic agent skills (no ROM-specific addresses). New repo: `msx-scaffold`. After bootstrap, `msx-code-data` |
| `scaffold/` | Templates copied by `bin/scaffold` |

## Vocabulary

- **Bank** — 8 KiB mapper unit. Scaffold: one `banks/bankNN.asm`. After the
  pager is known, contiguous banks become one window file (`konami-msx-disasm`).
- **CPU page** — 16 KiB MSX slot page.
- **Window file** — one `.asm` + matching `.blocks` for banks this cart maps
  together (triplet, pair, …). Stem `banks_` + concatenated hex ids.
- **Segment** — do not use in new text (collides with z80dasm / sjasmplus).

## Placement

If a helper would apply to a second MSX/Konami cart, it lives here. If it names
one ROM’s stems, RAM, banks, or dumpers, it stays in that game repo.

## Skills

```
bin/install-skills    # symlink skills/* -> <project>/.cursor/skills/; drop stale
bin/add-skill NAME    # create skills/NAME + install
```

Agents follow `skills/` (and this repo’s `AGENTS.md`) in addition to a game’s
`.agents/skills/`. Record workbench / CocoaMSX changes in **this** tree, not
in a game’s `docs/progress.md`. CocoaMSX research-display notes:
`cocoamsx/tools/disasm/README.md` and skill `msx-cocoamsx`.

## License

Original work here is Apache 2.0 (`LICENSE`, `NOTICE`).

`cocoamsx/` is the CocoaMSX / blueMSX emulator with DISASMTRACE patches and is
**not** Apache-licensed; keep its existing notices. Do not copy game ROMs into
this repository.
