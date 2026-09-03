# Workbench tool reference

These pages document the standalone helpers engineers launch to set up an
MSXDAW project, inspect a ROM, regenerate assembly, and render known data
formats. Each page starts with the task the helper performs, then gives its
prerequisites, exact syntax, arguments, outputs, and practical failure modes.

Run game-aware helpers from the game repository or one of its descendants.
Most of them locate the project through `workbench.cfg`; when working
elsewhere, set `GAME` to the game root. Examples use cart-neutral names and
addresses that must be replaced with values established for the cart under
analysis.

## Repository setup

- [`probe`](tools/probe.md) — inspect a ROM before choosing its mapper and
  scaffold layout.
- [`scaffold`](tools/scaffold.md) — create a new byte-exact game-disassembly
  repository.
- [`install-sjasmplus`](tools/install-sjasmplus.md) — build and install the
  assembler version expected by the workbench.
- [`install-skills`](tools/install-skills.md) — expose workbench skills in a
  project and remove stale links.
- [`add-skill`](tools/add-skill.md) — create a reusable workbench skill
  skeleton.

## Disassembly and analysis

- [`regen-bank.sh`](tools/regen-bank.md) — regenerate one 8 KiB bank with
  z80dasm.
- [`bank_sym.py`](tools/bank-sym.md) — prepare bank-specific z80dasm symbols
  and audit overlapping labels.
- [`strip-listing.py`](tools/strip-listing.md) — remove z80dasm listing tails
  from generated assembly.
- [`split-rom.sh`](tools/split-rom.md) — refresh scaffold bank binaries and
  remove migrated leftovers.
- [`romscan.py`](tools/romscan.md) — find static references and decode dispatch
  tables.
- [`coverage.py`](tools/coverage.md) — report disassembly progress and produce
  badge data.
- [`gfxview.py`](tools/gfxview.md) — inspect binary graphics as terminal ASCII
  art.

## Graphics and audio formats

- [`rledec.py`](tools/rledec.md) — decompress Konami VRAM RLE streams.
- [`rleenc.py`](tools/rleenc.md) — encode a contiguous buffer as Konami VRAM
  RLE.
- [`psgplay.py`](tools/psgplay.md) — render Konami 6-byte, three-channel PSG
  records.
- [`sccplay.py`](tools/sccplay.md) — render Konami 18-byte packed AY+SCC
  streams.
- [`taitoplay.py`](tools/taitoplay.md) — render the supported Taito
  `psg_play` format.

## Other workbench interfaces

Reusable Python modules such as `lib/game.py` and `msx/pngwrite.py` are support
libraries rather than task-facing helpers, so they are not part of this CLI
reference.

The instrumented CocoaMSX research display is documented separately in
[`cocoamsx/tools/disasm/README.md`](../cocoamsx/tools/disasm/README.md).
