#!/usr/bin/env bash
# Copyright 2026 Akop Karapetyan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Regenerate one 8 KiB bank from the game ROM via z80dasm.
#
#   regen-bank.sh <bank-number> [origin-hex] [blockfile]
#
# Origin defaults to workbench.cfg bank_org. Writes gitignored scratch:
#   generated/<prefix>NN.raw.asm
#   generated/<prefix>NN.generated.asm   fold THIS into committed source
set -euo pipefail
MSX="$(cd "$(dirname "$0")" && pwd)"
DAW="$(cd "$MSX/.." && pwd)"
export PYTHONPATH="${DAW}/lib${PYTHONPATH:+:$PYTHONPATH}"

if [ $# -lt 1 ]; then
  echo "usage: regen-bank.sh <bank> [origin-hex] [blockfile]" >&2
  exit 2
fi
bank="$1"
org="${2:-}"
blocks="${3:-}"

root="$(python3 "$DAW/lib/game.py" --root)"
cd "$root"

if [ -z "$org" ]; then
  org="$(python3 "$DAW/lib/game.py" --bank-org "$bank")"
fi
prefix="$(python3 "$DAW/lib/game.py" --get bank_prefix)"
[ -n "$prefix" ] || prefix=bank
nn=$(printf "%02d" "$bank")
stem="${prefix}${nn}"

rom="$(python3 "$DAW/lib/game.py" --rom)"
[ -f "$rom" ] || { echo "no ROM at $rom (run make, or set ROM=)" >&2; exit 1; }
master="$(python3 "$DAW/lib/game.py" --master)"
master_name="$(basename "$master")"

tmpbin="$(mktemp)"
python3 -c "
import sys
sys.path.insert(0, '${DAW}/lib')
from game import load
from pathlib import Path
g = load()
rom = Path('${rom}').read_bytes()
bank = int('${bank}')
off = bank * g.bank_size
Path('${tmpbin}').write_bytes(rom[off:off + g.bank_size])
"

mkdir -p generated
python3 "$MSX/bank_sym.py" "$bank"
sym="generated/${stem}.z80dasm.sym"

args=(-a -t -l -g "$org" -S "$sym")
[ -n "$blocks" ] && args+=(-b "$blocks")

raw="generated/${stem}.raw.asm"
gen="generated/${stem}.generated.asm"

z80dasm "${args[@]}" "$tmpbin" -o "$raw"
rm -f "$tmpbin"
sed -i '' "s/^	org .*/; (org set by PHASE in ${master_name})/" "$raw"

cp "$raw" "$gen"
python3 "$MSX/strip-listing.py" "$gen"
echo "wrote $gen (clean, fold this)  +  $raw (raw listing, temporary reference)"
