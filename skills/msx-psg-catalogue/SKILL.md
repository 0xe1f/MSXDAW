---
name: msx-psg-catalogue
description: >-
  Build labelled WAV catalogues for Konami packed-PSG BGM and SFX. Preview
  only; labelled .asm stays authoritative (make verify). Use when adding
  make music / make sfx, dumping tracks, or wrapping a game-specific player.
---

# MSX packed-PSG catalogues (guidelines)

WAV is preview only. Compressed / labelled `.asm` bytes stay authoritative
(`make verify`). Implement the wrapper in the **game** repo (`tools/psgplay.py`
+ `make music` / `make sfx`). Point it at a workbench player:

| Driver | Player | Typical layout |
|--------|--------|----------------|
| 6-byte music-rec (Vampire Killer `sound_tick`) | `konami/psgplay.py` | 3 PSG channels |
| 18-byte packed header, 8 slots (King's Valley II) | `konami/sccplay.py` | 3 PSG + 5 SCC |

Do not point the VK player at an 18-byte header table. Catalogue **names** and
default output dirs stay in the game wrapper. No extra audio libraries.

## Directories

| Dir | Contents |
|-----|----------|
| `music/` | looping / staged BGM (`{id}_{name}.wav`) |
| `sfx/` | one-shot effects (`{id}_{name}.wav`) |

Do not mix the two. Id is **2 uppercase hex digits**, then an underscore and a
short stem from the call site (`05_bgm_stage`, `3C_fall`). Rename the WAV when
the call site is named.

## Regeneration

`make music` / `make sfx` rebuild from the assembled ROM (same as `make gfx`).
Add / rename / delete a stream in `banks/data/psg*.asm` → the WAV goes with it
once you re-run the target. WAVs are tracked so they are audible without a
rebuild, like `gfx/` PNGs.

Hard caps (fade heuristics, loop counts) live on the player CLI; the game
wrapper supplies per-cart `--map` / table addresses / id lists.
