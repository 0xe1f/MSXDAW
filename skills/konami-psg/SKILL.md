---
name: konami-psg
description: >-
  Render Konami packed-PSG bytecode to WAV via tools/workbench/konami/psgplay.py.
  Use when dumping BGM or SFX, pointing --map at sound banks, or wrapping a
  game-specific catalogue (tools/psgplay.py in the game repo).
---

# Konami packed-PSG

AY-3-8910 timing (fmaster/8). Recognizable, not analog-accurate. Point `--map`
and table addresses at the game’s sound banks. Catalogue names and default
output dirs stay in the **game** `tools/psgplay.py`.

```
tools/workbench/konami/psgplay.py Game.rom --map 14@8000,15@a000 \
    --music-ptr 0x8DC9 --sfx-ptr 0x8D8D \
    --env-ptr 0xAAD6 --env-alt 0xAAEE --note-tbl 0x8B81 \
    --music-ids 0x80-0x8E
```

Not SCC wavetable (add a Konami SCC helper when a cart needs it).

## Driver bank

Packed-PSG payload often follows a word table indexed by `id*2`. The table
may overlap the last `ld (9000h),a / ret` of the SCC page restore (`table[0]`
unused; `table[1]` = first stream). Mark `worddata` from the first exclusive
entry; mark the rest of that bank (and often the next triplet window)
`bytedata` until streams are named. SCC enable is `ld a,3Fh / ld (9000h),a`;
wavetable copy is 32 bytes into `9800` + n*0x20.
