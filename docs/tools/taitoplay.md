# `taitoplay.py`

Render one play ID from the supported Taito `psg_play`/`psg_tick` bytecode
format to a WAV file. Use it for carts with the same linear 32 KiB CPU window,
page-`0xB4` index, five-byte records, and two-slot driver layout.

This is not a generic PSG stream decoder and is not compatible with Konami
packed-PSG data. The helper does not use `workbench.cfg`.

## Prerequisites

- Python 3.
- A linear ROM image containing the expected Taito tables and streams.
- The workbench `konami/psgplay.py`, imported for its AY-3-8910 model and WAV
  writer.

No third-party Python audio packages are required.

## Syntax

```sh
tools/workbench/msx/taitoplay.py ROM --id ID \
  [--sfx] [--loops N] [--min-seconds S] [--seconds S] \
  [--rate HZ] [-o DIR] [--base ADDR]
```

Arguments and defaults:

- `ROM` is the linear ROM image path.
- `--id ID` is required. It accepts decimal or `0x`-prefixed hexadecimal.
- `--sfx` selects one-shot rendering heuristics. Default: BGM heuristics.
- `--loops N` stops looping BGM after at least `N` detected inner-loop hits
  and the minimum duration. Default: `8`. It does not stop SFX.
- `--min-seconds S` is the minimum BGM duration before the loop heuristic may
  stop playback. Default: `20.0`. It does not stop SFX.
- `--seconds S` sets a hard playback cap before the final fade. Default:
  `90.0` seconds for BGM and `4.0` seconds for SFX.
- `--rate HZ` sets WAV sample rate. Default: `22050`.
- `-o DIR`, `--out DIR` selects the output directory. Default: current
  directory (`.`). Missing directories are created.
- `--base ADDR` maps ROM file offset zero to this CPU address. It accepts
  decimal or `0x` hexadecimal. Default: `0x4000`.
- `-h`, `--help` prints command help.

## Render BGM

```sh
tools/workbench/msx/taitoplay.py cart.rom --id 0x01 -o music
```

The output filename defaults to the two-digit uppercase hexadecimal ID:

```text
music/01.wav
```

The command prints the ID, filename stem, rendered duration, and path. BGM
normally stops when the stream becomes inactive, when the loop and minimum
duration thresholds are both met, or at the hard cap. It then applies an
approximately one-second fade.

Force a 12-second preview at 44.1 kHz:

```sh
tools/workbench/msx/taitoplay.py cart.rom --id 1 \
  --seconds 12 --rate 44100 -o previews
```

## Render an SFX

```sh
tools/workbench/msx/taitoplay.py cart.rom --sfx --id 0x81 -o sfx
```

SFX mode uses a default four-second hard cap and an approximately 0.12-second
fade. `--loops` and `--min-seconds` do not control SFX termination.

The WAV is mono, 16-bit signed PCM at the selected sample rate. Generated WAVs
are previews; compressed labelled assembly remains authoritative.

## Format and mapping constraints

The player expects CPU-visible content through `0xB4xx`, including its fixed
index and envelope locations. With the default base, a normal input is a
linear image mapped from `0x4000` through `0xBFFF`. `--base` only changes the
CPU-to-file offset relationship; it does not relocate the expected tables.

The AY synthesis follows the workbench's shared CocoaMSX/blueMSX-derived model.
It is suitable for recognizable catalogues, not analog-accurate reproduction.

## Errors and gotchas

- A missing ROM exits with `no ROM: <path>`.
- Omitting `--id` exits with `pass --id`.
- IDs are masked to eight bits when sent to the emulated driver. Keep IDs in
  `0x00` through `0xFF`; larger or negative values can produce misleading
  filenames and select a different byte value.
- The helper does not validate that the ROM actually has the expected driver
  layout. Out-of-range reads return zero, so a wrong image or base can produce
  silence or misleading output instead of an explicit error.
- `--seconds` is a cap, not a guaranteed duration. A naturally inactive stream
  can stop earlier after two silent frames and its fade.
- The final fade extends output beyond the selected hard cap.
- Nonpositive sample rates, unreasonable durations, or negative loop values
  are not validated and may fail or behave unexpectedly.
- This standalone CLI renders one ID per invocation and has no naming map.
  A cart-specific wrapper should provide catalogue ID lists and stable names.
- Do not point `konami/psgplay.py` or `konami/sccplay.py` at this Taito format,
  and do not point this helper at Konami streams.

## Related helpers and skills

- `konami/psgplay.py` provides the shared AY model and handles Konami's
  six-byte music-record format.
- `konami/sccplay.py` handles Konami packed PSG+SCC streams.
- Skills: `msx-psg-catalogue`; use a game-specific wrapper for `make music`
  and `make sfx`.
