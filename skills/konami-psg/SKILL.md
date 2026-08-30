---
name: konami-psg
description: >-
  Render Konami packed-PSG bytecode to WAV. Use when dumping BGM or SFX,
  choosing psgplay.py vs sccplay.py, or wrapping a game-specific catalogue
  (tools/psgplay.py in the game repo). Catalogue layout is msx-psg-catalogue.
---

# Konami packed-PSG

AY-3-8910 timing (fmaster/8). Recognizable, not analog-accurate. Catalogue
names and default output dirs stay in the **game** `tools/psgplay.py`
(`msx-psg-catalogue`).

Taito carts (`psg_play` / 5-byte records / two slots) use
`msx/taitoplay.py`, not these players.

Two in-house Konami drivers; pick the player that matches the header:

## 6-byte music-rec (Vampire Killer)

3 PSG channels. `play_sound` copies a 20-byte template per channel.

```
tools/workbench/konami/psgplay.py Game.rom --map 14@8000,15@a000 \
    --music-ptr 0x8DC9 --sfx-ptr 0x8D8D \
    --env-ptr 0xAAD6 --env-alt 0xAAEE --note-tbl 0x8B81 \
    --music-ids 0x80-0x8E
```

## 18-byte packed header (King's Valley II / SCC)

8 slots (3 AY + 5 SCC). `sound_play` copies 18 bytes from `ptr[id*2]`; packed
header is `db flags, pri` then one `dw` per SET bit (bit 7 first). Channel
bytecode is not the VK opcode set.

```
tools/workbench/konami/sccplay.py Game.rom --map 4@6000,5@8000,6@A000 \
    --ptr 0x6F2E --id 5
```

SCC enable is `ld a,3Fh / ld (9000h),a`; wavetable copy is 32 bytes into
`9800` + n×0x20 (channel 5 shares channel 4’s wave).

## Driver bank

Packed-PSG payload often follows a word table indexed by `id*2`. The table
may overlap the last `ld (9000h),a / ret` of the SCC page restore (`table[0]`
unused; `table[1]` = first stream). Mark `worddata` from the first exclusive
entry; mark the rest of that bank (and often the next triplet window)
`bytedata` until streams are named.
