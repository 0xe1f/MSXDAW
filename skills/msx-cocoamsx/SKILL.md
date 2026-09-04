---
name: msx-cocoamsx
description: >-
  How to use workbench CocoaMSX as a research display: launch, JSON config,
  accelerated present toggle, control socket (peek/watch/snap/loadstate/keys),
  savestates, snapshot diffs. Use when tracing an MSX ROM, watching work-RAM,
  or driving the emulator from an agent. Not for static romscan / .asm edits.
---

# MSXDAW CocoaMSX (research display)

The instrumented emulator is `tools/workbench/cocoamsx/` (or
`~/code/msxdaw/cocoamsx/` in the canonical clone). ROM, snapshots, and logs
stay in the **game** repo (`generated/`).

This is a display plus a text control surface, not a settings-heavy
emulator. Human keyboard/gamepad still work in the window. Agent control is
extra.

## When to use this vs static analysis

Use CocoaMSX when you need **live** behaviour: what a RAM byte does, which
PC writes it, what happens after a shot / room change / death. Prefer
`romscan` / reading `.asm` when the question is "who calls this" or "what is
this table". Snapshots find *where*; a tight WATCH finds the *writer PC*;
xref finds callers.

## Launch

```
tools/workbench/cocoamsx/tools/disasm/build-cocoamsx.sh
tools/workbench/cocoamsx/tools/disasm/trace-run.sh
COCOAMSX_ROM2=/path/to/GameMaster.rom tools/workbench/cocoamsx/tools/disasm/trace-run.sh
tools/workbench/cocoamsx/tools/disasm/cocoamsx-ctl peek c000
tools/workbench/cocoamsx/tools/disasm/snapdiff.py generated/disasmsnap.bin
```

`trace-run.sh` finds the game via `workbench.cfg` (cwd or `GAME=`). Pass a ROM
path to override. `COCOAMSX_ROM2` inserts a second cartridge in slot 2 before
the startup ROM boots (game + a slot-2 companion cart).

**Never kill a running emulator** (`kill`, `pkill`, closing the window)
unless the user asks. They are often mid-recording.

Keys are window-focused AppKit events. No Input Monitoring / Accessibility
prompt. Rebuilds do not need a TCC grant.

### Config (JSON)

Search order: `COCOAMSX_CONFIG`, `./cocoamsx.json`, `~/.config/cocoamsx/config.json`.
Example: `tools/workbench/cocoamsx/cocoamsx.json.example`.

| key | default | live reload |
|-----|---------|-------------|
| `machine` | `MSX2 - C-BIOS` | no (cold reboot) |
| `volume` | 75 | yes |
| `scale` | 2 | no (window size at launch) |
| `accelerated` | true | yes |
| `vdp_sync` | `60hz` | no (pinned NTSC 60Hz) |
| `speed` | 100 | yes |
| `socket` | `/tmp/cocoamsx.sock` | no |
| `snap_range` | `c000-dfff` | env at launch |

Reload: `cocoamsx-ctl reload-config` or SIGHUP. Env `COCOAMSX_ACCELERATED=0`
overrides JSON for one run (CPU `drawRect` present if CALayer/Metal
misbehaves). Both presents are nearest-neighbor; off is a fallback, not a
quality setting.

## Seek, don't play

Do not TAS from the Konami logo. Named savestates live in the **game** repo
(`generated/` or `research/*.sta`):

```
cocoamsx-ctl savestate generated/scene.sta
cocoamsx-ctl loadstate generated/scene.sta
```

Trainer cart / RAM poke only when a state is missing. The human can still
play in the window; the agent should load a state and observe.

## Observe

Snapshots first, then a tight watch:

1. `snap` (or F9) before an action, `snap` after. F8 / `autosnap on` for a
   per-frame recording (red dot in the corner).
2. `snapdiff.py generated/disasmsnap.bin` / `--track c000` to see which
   bytes moved.
3. `watch c000` and repeat the action for the writer PC (`W ss:pppp aaaa=vv`).
4. `peek c000` / `dump c000 80` / `wait c000 == 05` when you already know the
   address. `screenshot /tmp/frame.png` when RAM is ambiguous.

Keep `DEDUP=1`. Do not broad-EXEC; it explodes the log. Changing WATCH no
longer needs a relaunch (`cocoamsx-ctl watch …`).

Record the baseline snapshot count before the user records so you only
analyze new frames.

## Drive a few frames

Same inject path as the human (macOS virtual key codes via the responder
chain):

```
cocoamsx-ctl key down space
cocoamsx-ctl key up space
cocoamsx-ctl hold right 30
cocoamsx-ctl wait c000 == 80
cocoamsx-ctl snap
```

Names: `up down left right space shift ctrl alt z x a s enter esc tab f8 f9`.
Use this for "fire once", not for crossing a stage.

## cocoamsx-ctl cheat sheet

Socket: `COCOAMSX_SOCKET` (default `/tmp/cocoamsx.sock`). One line in, one
line out (`ok …` / `err …`).

| command | effect |
|---------|--------|
| `ping` | `ok pong` |
| `peek c000` | one byte |
| `dump c000 80` | hex bytes (len hex or decimal) |
| `watch c000-c01f` | live WATCH ranges (same grammar as env) |
| `exec 4000-4010` | live EXEC ranges |
| `snap` | one RAM snapshot (same file as F9) |
| `autosnap on\|off` | per-frame snapshots (F8) |
| `wait addr == xx [ms]` | block until RAM matches (default 30s) |
| `key down\|up name` | inject |
| `hold name frames` | down, sleep ~frames/60, up |
| `loadstate path` | `emulatorStart` savestate |
| `savestate path` | `boardSaveState` |
| `screenshot path.png` | PNG of the current frame |
| `pause` / `resume` | emulator pause |
| `accelerated on\|off` | GPU vs CPU present |
| `reload-config` | re-read JSON |

## Gotchas

- Emulation **does not pause** when the window is in the background.
  `peek` / `dump` / `wait` work without focusing the window. Explicit
  `cocoamsx-ctl pause` still stops the CPU.
- **`pause` then `peek`/`dump`/`wait` deadlocks.** Those verbs wait for the
  next opcode fetch; a paused CPU never fetches. `resume` first, or
  `screenshot` without peeking.
- zsh: quote `wait` (`cocoamsx-ctl wait 'c000' '==' '02'`). `==` is special.
- Do not restore `glBegin` OpenGL / `COCOAMSX_SOFTWARE_GL` — crashes in
  Apple’s Metal GL shim. `accelerated: false` is the CPU `drawRect` fallback;
  that blit must not extra Y-flip (FAST buffer is already top-down).
- About’s credits scroller used to recurse until SIGSEGV (document-height
  wrap). Fixed in `CMAboutController`; rebuild if a binary still dies on About.
- Do not restore `NSApplicationPresentationDisableProcessSwitching` on
  key window — it blocked Spaces / Mission Control while focused.
- Prefs / Sparkle / hq2x stay in the Xcode target (unhooked, not deleted).

Emulator how-to lives in this skill and `cocoamsx/tools/disasm/README.md`.
Game `docs/progress.md` is ROM findings only.

## Cost discipline

- Snapshots are the cheap primary tool. WATCH is for writer PCs, kept tight.
- Never relaunch just to change WATCH/EXEC.
- Ask before interrupting the GUI.
- Confirm the process env if a launch looks wrong:
  `pgrep -f CocoaMSX`; `ps eww -p <pid> -o command= | tr ' ' '\n' | grep DISASM`
  (may need full permissions).
