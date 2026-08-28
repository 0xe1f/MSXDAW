---
name: msx-romscan
description: >-
  Static xref and dispatch-table decode for banked Z80 ROMs via
  tools/workbench/msx/romscan.py. Use when finding callers of an address,
  decoding a jump or handler table, asking who calls or jumps to a routine,
  grepping leftover bins for references, or writing ad-hoc xref python.
---

# MSX romscan

Prefer this over grepping `.bin` files or a one-off Python xref. Needs a built
`<Game>.rom` and `workbench.cfg`. Default scan set is cfg `scan_banks`.

```
tools/workbench/msx/romscan.py xref 0xADDR
tools/workbench/msx/romscan.py xref 0xADDR --banks 2,3
tools/workbench/msx/romscan.py table 0xADDR --words N
tools/workbench/msx/romscan.py table 0xADDR --bytes N
tools/workbench/msx/romscan.py table 0xADDR --words N --index-base 1
tools/workbench/msx/romscan.py --rom other.rom xref 0x4000
```

`--index-base 1` when the dispatcher does `dec a`. `--base` overrides the CPU
origin for paged banks.

## `code` vs `data?`

- **`code`** — real `call` / `jp` / `jr` / `djnz`
- **`data?`** — bare little-endian word (pointer table or coincidence)

No `code` xref ≠ dead: the entry may be a stored/computed pointer. Cross-bank
`call` from the resident window into `0x8000`/`0xA000` is normal.
