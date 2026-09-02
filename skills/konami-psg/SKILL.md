---
name: konami-psg
description: >-
  Render Konami packed-PSG bytecode to WAV. Use when dumping BGM or SFX,
  choosing psgplay.py vs sccplay.py, or wrapping a game-specific catalogue
  (tools/psgplay.py in the game repo). Catalogue layout is msx-psg-catalogue.
---

# Konami packed-PSG

AY generators match CocoaMSX ``AY8910.c`` (blueMSX). Recognizable, not
analog-accurate. Catalogue names and default output dirs stay in the **game**
`tools/psgplay.py` (`msx-psg-catalogue`).

Taito carts (`psg_play` / 5-byte records / two slots) use
`msx/taitoplay.py`, not these players.

Two in-house Konami drivers; pick the player that matches the header:

## 6-byte music-rec

3 PSG channels. The driver copies a 20-byte template per channel.

```
tools/workbench/konami/psgplay.py Game.rom --map 2@8000,3@a000 \
    --music-ptr <cpu> --sfx-ptr <cpu> \
    --env-ptr <cpu> --env-alt <cpu> --note-tbl <cpu> \
    --music-ids <range>
```

## 18-byte packed header (SCC)

8 slots (3 AY + 5 SCC). Play copies 18 bytes from `ptr[(id-1)*2]`; packed
header is `db flags, pri` then one `dw` per SET bit (bit 7 first). Channel
bytecode is not the 6-byte opcode set.

```
tools/workbench/konami/sccplay.py Game.rom --map 1@6000,2@8000,3@A000 \
    --ptr <cpu> --id 1
```

SCC enable is `ld a,3Fh / ld (9000h),a`; wavetable copy is 32 bytes into
`9800` + n×0x20 (channel 5 shares channel 4’s wave).

## Driver bank

Packed-PSG payload often follows a word table indexed by `id*2`. The table
may overlap the last `ld (9000h),a / ret` of the SCC page restore (`table[0]`
unused; `table[1]` = first stream). Mark `worddata` from the first exclusive
entry; mark the rest of that bank (and often the next triplet window)
`bytedata` until streams are named.
