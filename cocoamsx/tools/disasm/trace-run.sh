#!/usr/bin/env bash
# Run the DISASMTRACE CocoaMSX build. F9 dumps a RAM snapshot; F8 toggles auto-snap.
#
#   tools/disasm/trace-run.sh [rom]
#
# Game repo from workbench.cfg (cwd walk or GAME=).
# Snapshots and the exec/watch log land in the game's generated/ (gitignored there).
#
# Environment knobs (all optional):
#   GAME   game repo (default: walk for workbench.cfg)
#   EXEC   exec address ranges, e.g. "4000-4010"
#   WATCH  memory-write ranges, e.g. "c000-c01f"
#   LOG    trace log
#   SNAP   snapshot file
#   SNAPRANGE  RAM window per snapshot (default c000-dfff)
#   DEDUP  0 = log every executed address (default 1)
#   COCOAMSX_ACCELERATED  0 = CPU drawRect present (default: GPU CALayer)
#   COCOAMSX_SOCKET       control socket (default /tmp/cocoamsx.sock)
#   COCOAMSX_CONFIG       JSON config path
#   COCOAMSX_ROM2         second cartridge (slot 2) inserted before autostart
set -euo pipefail
src="$(cd "$(dirname "$0")/../.." && pwd)"
daw="$(cd "$src/.." && pwd)"
export PYTHONPATH="${daw}/lib${PYTHONPATH:+:$PYTHONPATH}"
if python3 "$daw/lib/game.py" --root >/dev/null 2>&1; then
  game="$(python3 "$daw/lib/game.py" --root)"
  default_rom="$(python3 "$daw/lib/game.py" --rom)"
else
  echo "no game repo (workbench.cfg or GAME=)" >&2
  exit 1
fi

app="$src/generated/cocoamsx-dd/Build/Products/Debug/CocoaMSX.app/Contents/MacOS/CocoaMSX"
if [ ! -x "$app" ]; then
    echo "traced build not found - run $src/tools/disasm/build-cocoamsx.sh first" >&2
    exit 1
fi

rom="${1:-$default_rom}"
log="${LOG:-$game/generated/disasmtrace.log}"
snap="${SNAP:-$game/generated/disasmsnap.bin}"
mkdir -p "$(dirname "$log")" "$(dirname "$snap")"

echo "app        $app"
echo "rom        $rom"
echo "trace log  $log   (exec='${EXEC:-}' watch='${WATCH:-}')"
echo "snapshots  $snap  (F9 capture; range ${SNAPRANGE:-c000-dfff})"
echo "socket     ${COCOAMSX_SOCKET:-/tmp/cocoamsx.sock}"
export DISASM_TRACE=1
export DISASM_DEDUP="${DEDUP:-1}"
export DISASM_EXEC="${EXEC:-}"
export DISASM_WATCH="${WATCH:-}"
export DISASM_LOG="$log"
export DISASM_SNAP="$snap"
export DISASM_SNAP_RANGE="${SNAPRANGE:-c000-dfff}"
export COCOAMSX_SOCKET="${COCOAMSX_SOCKET:-/tmp/cocoamsx.sock}"
exec "$app" "$rom"
