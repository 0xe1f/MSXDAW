# `sccplay.py` — render Konami packed AY + SCC audio

Use `konami/sccplay.py` to render a Konami **18-byte packed-header** audio
driver into WAV files. This format has eight slots: three AY-3-8910 PSG
channels followed by five Konami SCC wavetable channels.

This is not the 6-byte, three-PSG-channel music-record format handled by
[`psgplay.py`](psgplay.md). The header layout and channel bytecode are
different, even when both formats appear in Konami carts. It is also not the
Taito 5-byte `psg_play` format.

The output is intended for identification and catalogue previews. It is
recognizable, not analog-accurate.

## Prerequisites

- Python 3; no third-party packages are required.
- A ROM image using this 18-byte driver family.
- The active 8 KiB ROM-bank map.
- The CPU address of the 1-based header pointer table.
- A map that covers the selected header, all referenced channel streams, and
  the renderer's driver tables at these fixed CPU addresses:
  - note table: `0x6480`;
  - SCC wavetable pointer table: `0x7210`;
  - envelope tables: `0x76A0`, `0x77E1`, `0x77FA`, `0x7813`, `0x782C`,
    and `0x7845`.

Those fixed addresses are part of this helper's supported driver layout; they
cannot be changed on the command line. A cart that relocates them needs an
adapted renderer, even if its outer header looks similar.

Each pointer-table entry addresses an 18-byte packed header: one flags byte,
one priority byte, then one little-endian stream pointer for each set channel
flag, in bit-7-to-bit-0 order.

## Syntax

```text
tools/workbench/konami/sccplay.py ROM --map MAP --ptr CPU
    [--sfx]
    [--id ID | --ids FIRST-LAST]
    [--name ID=STEM ...]
    [--loops N] [--min-seconds SECONDS] [--seconds SECONDS]
    [--rate HZ] [-o DIR]
```

Select at least one ID with `--id` or `--ids`.

## Arguments and options

- `ROM` — input ROM image. Required.
- `--map MAP` — required, comma-separated `BANK@CPU` mappings for 8 KiB
  windows, for example `1@6000,2@8000,3@A000`. Bank numbers accept
  Python-style integers such as `1` or `0x1`; CPU window bases are interpreted
  as hexadecimal, so both `6000` and `0x6000` work.
- `--ptr CPU` — required CPU address of the little-endian packed-header pointer
  table. ID `1` selects its first word, ID `2` its second, and so on.
- `--sfx` — use one-shot timing: a 4-second default cap, no minimum duration,
  and a short ending fade. It does not select a different pointer table or
  bytecode format. Default: BGM timing.
- `--id ID` — render one 1-based ID. If present, it takes precedence over
  `--ids`.
- `--ids FIRST-LAST` — render an inclusive, ascending ID range, for example
  `1-0x10`.
- `--name ID=STEM` — replace the default two-digit uppercase hexadecimal
  filename stem for one ID. Repeat for multiple IDs. Later entries for the
  same ID win.
- `--loops N` — begin the BGM fade after this many `0xFD` absolute-jump
  commands, subject to `--min-seconds`. Default: `2`; values below `1` behave
  as `1`. The `0xFB` and `0xFC` byte-loop commands do not increment this
  counter. Ignored for SFX stopping.
- `--min-seconds SECONDS` — minimum BGM playback before loop-based stopping.
  Default: `20.0`. In SFX mode it is forced to zero. Naturally ending tracks
  may stop earlier.
- `--seconds SECONDS` — hard playback cap. Default: `90.0` for BGM and `4.0`
  for SFX.
- `--rate HZ` — WAV sample rate. Default: `22050`.
- `-o DIR`, `--out DIR` — output directory. Default: the current directory.
  Missing output directories are created.

IDs and CPU addresses use Python's base-aware integer syntax, so decimal and
`0x`-prefixed values are accepted. A range must contain one hyphen.

## Examples

Render one BGM:

```sh
tools/workbench/konami/sccplay.py Cart.rom \
  --map 1@6000,2@8000,3@a000 \
  --ptr 0x7c20 --id 1 --name 1=01_opening -o music/
```

Render a range with a shorter preview cap:

```sh
tools/workbench/konami/sccplay.py Cart.rom \
  --map 1@6000,2@8000,3@a000 \
  --ptr 0x7c20 --ids 1-0x18 --seconds 30 -o music/
```

Render one ID with one-shot timing:

```sh
tools/workbench/konami/sccplay.py Cart.rom \
  --map 1@6000,2@8000,3@a000 \
  --ptr 0x7c20 --sfx --id 0x19 --name 0x19=19_hit -o sfx/
```

The pointer address and bank numbers above are placeholders. The shown CPU
windows deliberately cover the helper's fixed driver tables; derive the actual
active banks and header table from the cart.

## Output and stopping behavior

One mono, 16-bit PCM WAV is written per ID at the selected sample rate. Without
`--name`, ID `10` becomes `0A.wav`. Each render prints its ID, stem, duration,
and output path.

BGM playback stops when all slots become idle, the chosen jump-loop count is
reached after the minimum duration, or the hard cap is reached, then fades for
about one second. SFX playback stops when all slots become idle or reaches its
cap, then uses a short fade.

The SCC model renders five channels with 32-byte signed wavetables. SCC channel
5 shares channel 4's wavetable, matching the hardware arrangement.

## Errors and gotchas

- `no ROM: ...` — the ROM path does not name a regular file.
- `pass --id or --ids` — no ID selection was supplied.
- `map entry ...: want BANK@CPU` — a map component lacks `@`.
- `empty --map` — the map contains no windows.
- `music pointer ... is outside the mapped banks` — a header, stream, or fixed
  driver table is not covered. Correct the active bank mapping; table options
  are CPU addresses, not ROM file offsets.
- `empty id range ...` — the range end is below its start.
- `--name wants ID=STEM` — the `=` or one side of the mapping is missing.
- IDs are 1-based. ID `0` indexes the word before the declared table and is not
  a valid first entry.
- `--id` overrides `--ids`. `--sfx` changes stopping and fade behavior only; it
  does not switch to a separate SFX pointer table.
- A command-loop error, mapping traceback, implausible duration, or badly
  distorted output usually indicates the wrong 18-byte driver variant, ID,
  pointer table, or active bank map.
- The renderer does not expose the fixed note, envelope, or wavetable tables as
  options. Confirm those addresses before treating an apparent render failure
  as corrupt audio data.
- Driver-triggered global fade modes are not fully modeled; the CLI's own
  stop-and-fade heuristics provide catalogue-length previews. Some tracks may
  therefore end differently from gameplay.
- WAV files are previews. Keep packed data authoritative and verify ROM edits
  separately.

## Related helpers and skills

- [`psgplay.py`](psgplay.md) — Konami 6-byte, three-AY-channel music records.
- `msx/taitoplay.py` — Taito 5-byte, two-slot PSG format.
- `konami-psg` — identify the driver layout and select the correct renderer.
- `msx-psg-catalogue` — build a cart-specific wrapper and labelled WAV
  catalogue while keeping cart addresses and names out of the workbench.
