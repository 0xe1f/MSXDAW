# `psgplay.py` — render Konami packed PSG audio

Use `konami/psgplay.py` to render BGM or sound effects from a Konami
**6-byte music-record** driver into WAV files. This format has three AY-3-8910
channels and a 20-byte per-channel state template.

Do not use it for:

- the Konami 18-byte packed-header format with 3 AY + 5 SCC channels; use
  [`sccplay.py`](sccplay.md);
- Taito `psg_play` / `psg_tick` data with 5-byte records and two slots; use
  `msx/taitoplay.py`.

The renderer is intended for identification and catalogue previews. Its AY
model follows CocoaMSX/blueMSX behavior closely enough to make tracks
recognizable, but it is not an analog-accurate recording.

## Prerequisites

- Python 3; no third-party packages are required.
- A ROM image.
- The 8 KiB ROM-bank mapping active when the driver reads the audio data.
- CPU addresses for all five required tables:
  - BGM records (`--music-ptr`);
  - SFX pointers (`--sfx-ptr`);
  - primary and alternate envelope pointers (`--env-ptr`, `--env-alt`);
  - the 12-entry note-period table (`--note-tbl`).

Addresses passed to table options are CPU addresses, not ROM file offsets.
Every referenced header, stream, envelope, and table must fall in a bank
window supplied by `--map`.

## Syntax

```text
tools/workbench/konami/psgplay.py ROM --map MAP
    --music-ptr CPU --sfx-ptr CPU --env-ptr CPU --env-alt CPU
    --note-tbl CPU
    [--sfx]
    [--id ID | --music-ids FIRST-LAST | --sfx-ids FIRST-LAST]
    [--name ID=STEM ...]
    [--loops N] [--min-seconds SECONDS] [--seconds SECONDS]
    [--rate HZ] [-o DIR] [--no-verify]
```

All five table options are required even when rendering only BGM or only SFX.
Select at least one ID with `--id`, or with the mode-appropriate range option.

## Arguments and options

- `ROM` — input ROM image. Required.
- `--map MAP` — required, comma-separated `BANK@CPU` mappings for 8 KiB
  windows, for example `2@8000,3@a000`. Bank numbers accept Python-style
  integers such as `2` or `0x2`; CPU window bases are interpreted as
  hexadecimal, so both `8000` and `0x8000` work.
- `--music-ptr CPU` — required CPU address of consecutive 6-byte BGM records.
  Each record contains three little-endian channel pointers. ID `0x80` selects
  record zero, `0x81` record one, and so on.
- `--sfx-ptr CPU` — required CPU address of the little-endian SFX pointer
  table. It is indexed as `ID * 2`; ID `1` is the first SFX and entry zero is
  unused.
- `--env-ptr CPU` — required CPU address of the primary envelope pointer table.
- `--env-alt CPU` — required CPU address of the alternate envelope pointer
  table.
- `--note-tbl CPU` — required CPU address of 12 little-endian note periods for
  one octave.
- `--sfx` — render SFX instead of BGM. Default: BGM.
- `--id ID` — render one ID. If present, it takes precedence over either range
  option. It does not select SFX mode by itself; combine it with `--sfx` for an
  effect.
- `--music-ids FIRST-LAST` — inclusive BGM ID range, for example
  `0x80-0x8f`. Used only when `--sfx` is absent.
- `--sfx-ids FIRST-LAST` — inclusive SFX ID range, for example `1-0x10`.
  Used only with `--sfx`.
- `--name ID=STEM` — replace the default two-digit uppercase hexadecimal
  filename stem for one ID. Repeat for multiple IDs. Later entries for the
  same ID win.
- `--loops N` — begin the BGM fade after this many `EA` loop jumps, subject to
  `--min-seconds`. Default: `2`; values below `1` behave as `1`. This option
  does not control SFX.
- `--min-seconds SECONDS` — minimum BGM playback before loop-based stopping.
  Default: `20.0`. Naturally ending tracks may stop earlier.
- `--seconds SECONDS` — playback horizon. Default: `90.0` for BGM and `4.0`
  for SFX. SFX stops at the horizon; BGM reserves an additional one-second
  fade window.
- `--rate HZ` — WAV sample rate. Default: `22050`.
- `-o DIR`, `--out DIR` — output directory. Default: the current directory.
  Missing output directories are created.
- `--no-verify` — skip the built-in comparison of `--note-tbl` against the
  expected 12 note periods. Verification is enabled by default in both BGM
  and SFX mode.

IDs, table addresses, and numeric timing/rate values use Python's normal
integer or floating-point syntax as appropriate. Integer IDs and addresses
accept decimal or a `0x` prefix. A range must be ascending and contain one
hyphen.

## Examples

Render one BGM record:

```sh
tools/workbench/konami/psgplay.py Cart.rom \
  --map 4@8000,5@a000 \
  --music-ptr 0x8120 --sfx-ptr 0x8240 \
  --env-ptr 0x8300 --env-alt 0x8340 --note-tbl 0x83c0 \
  --id 0x80 --name 0x80=80_title -o music/
```

Render an inclusive BGM range with a shorter preview cap:

```sh
tools/workbench/konami/psgplay.py Cart.rom \
  --map 4@8000,5@a000 \
  --music-ptr 0x8120 --sfx-ptr 0x8240 \
  --env-ptr 0x8300 --env-alt 0x8340 --note-tbl 0x83c0 \
  --music-ids 0x80-0x8f --seconds 30 -o music/
```

Render SFX IDs 1 through 16:

```sh
tools/workbench/konami/psgplay.py Cart.rom \
  --map 4@8000,5@a000 \
  --music-ptr 0x8120 --sfx-ptr 0x8240 \
  --env-ptr 0x8300 --env-alt 0x8340 --note-tbl 0x83c0 \
  --sfx --sfx-ids 1-0x10 --name 1=01_confirm -o sfx/
```

The addresses above are placeholders illustrating the required relationship;
derive the actual map and table addresses from the cart being researched.

## Output and stopping behavior

One mono, 16-bit PCM WAV is written per ID at the selected sample rate. Without
`--name`, ID `0x8a` becomes `8A.wav`. Each completed render prints:

- the ID and output stem;
- BGM channel A/B/C stream pointers, or the SFX stream pointer;
- rendered duration;
- output path.

BGM fades for about one second after natural completion or the selected loop
count. SFX fades briefly after its stream terminator or cap.

## Errors and gotchas

- `no ROM: ...` — the ROM path does not name a regular file.
- `pass --id or --music-ids` / `pass --id or --sfx-ids` — no selection was
  supplied for the active mode.
- `map entry ...: want BANK@CPU` — a map component lacks `@`.
- `empty --map` — the map contains no windows.
- `music pointer ... is outside the mapped banks` — a required CPU address is
  not covered. Add the correct active bank window; do not substitute a ROM
  file offset.
- `note table mismatch ...` — the selected table or mapping does not match this
  driver family. Recheck the address and active banks. Use `--no-verify` only
  when the variation is understood; note verification also runs for SFX.
- `empty id range ...` — the range end is below its start.
- `--name wants ID=STEM` — the `=` or one side of the mapping is missing.
- `command loop at ...` or an index/mapping traceback usually means the wrong
  driver format, table, bank map, or ID was supplied.
- `--id` overrides a supplied range. `--sfx` changes the driver path; an SFX
  numeric ID without `--sfx` is treated as a BGM ID.
- If BGM reaches `--seconds` without ending or hitting the selected loop count,
  the renderer runs through its reserved one-second tail without applying a
  gain fade. Expect a file about one second longer than the requested horizon.
- WAV files are previews. Keep the original packed bytes authoritative in the
  disassembly and verify ROM edits separately.

## Related helpers and skills

- [`sccplay.py`](sccplay.md) — Konami 18-byte, 3 AY + 5 SCC format.
- `msx/taitoplay.py` — Taito 5-byte, two-slot PSG format.
- `konami-psg` — choose the matching Konami driver and renderer.
- `msx-psg-catalogue` — wrap this helper in a cart-specific catalogue command;
  keep names, addresses, and default directories in the game repository.
