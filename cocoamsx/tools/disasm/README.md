# DISASMTRACE helpers

Build and run the instrumented CocoaMSX in this tree (`-DDISASMTRACE`).
This is a **research display**: nearest-neighbor present, JSON config, Unix
socket. Agent skill: `msx-cocoamsx`. Record further emulator changes here and
in that skill, not in a game’s `docs/`.

F9 dumps a work-RAM snapshot; F8 toggles auto-snap. `EXEC` / `WATCH` log
executed PCs and memory writes tagged with the paged ROM bank. The control
socket (`cocoamsx-ctl`) can change watches, peek RAM, inject keys, and
load savestates without a relaunch.

The game ROM, snapshot file, and exec/watch log stay in the **game** repo
(found via `workbench.cfg`, or `GAME=`).

```
tools/disasm/build-cocoamsx.sh
WATCH=c000-c01f tools/disasm/trace-run.sh
COCOAMSX_ROM2=/path/to/GameMaster.rom tools/disasm/trace-run.sh
tools/disasm/cocoamsx-ctl peek c000
tools/disasm/snapdiff.py generated/disasmsnap.bin
```

## Present

GPU CALayer `contents` (nearest) by default. `COCOAMSX_ACCELERATED=0` or JSON
`"accelerated": false` falls back to a CPU `drawRect:` blit. Both share the
FAST framebuffer (row 0 = top). CPU `drawRect` must **not** extra Y-flip
that buffer; CALayer `contents` already matches. Do **not** restore `glBegin`
OpenGL / `COCOAMSX_SOFTWARE_GL` — that path crashes in Apple’s Metal GL shim.

VDP is pinned NTSC 60 Hz (`P_VDP_SYNC60HZ`). `VIDEO_PAL_FAST` is blueMSX’s
no-filter blit name, not 50 Hz PAL.

## Input

Keys are window-focused AppKit events (`keyDown` / `injectKeyCode:`). No
IOHID keyboard monitor, no Input Monitoring permission. F8/F9 live on the
display view’s responder chain. Gamepad HID can still open.

Do not restore `NSApplicationPresentationDisableProcessSwitching` on key
window (upstream kiosk leftover). It blocked Mission Control / Spaces
while the emulator had focus.

## Config

Search order: `COCOAMSX_CONFIG`, `./cocoamsx.json`,
`~/.config/cocoamsx/config.json`. Example: `cocoamsx.json.example`. Reload
with `cocoamsx-ctl reload-config` or SIGHUP. Machine change is not hot.

Menus: Preferences / Sparkle Check for Updates are unhooked. About still
opens (credits wrap used to recurse until SIGSEGV; guarded in
`CMAboutController`).

## Socket gotchas

- `peek` / `dump` / `wait` complete on the **next opcode fetch**. `pause`
  then peek deadlocks (paused CPU never fetches). Resume first, or
  screenshot without peeking.
- zsh: quote `wait` (`cocoamsx-ctl wait 'c000' '==' '02'`). `==` is special.
