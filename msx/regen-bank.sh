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

# <bank> is decimal, or hex when bank_ids = hex; the rest of the script is decimal.
bank="$(python3 -c "
import sys
sys.path.insert(0, '${DAW}/lib')
from game import load
print(load().parse_bank_id('${bank}'))
")"

if [ -z "$org" ]; then
  org="$(python3 "$DAW/lib/game.py" --bank-org "$bank")"
fi
stem="$(python3 -c "
import sys
sys.path.insert(0, '${DAW}/lib')
from game import load
print(load().bank_stem(int('${bank}')))
")"

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
# z80dasm rejects block ranges outside this 8 KiB image. A window .blocks
# file lists every slice; keep entries whose start falls in this one.
if [ -n "$blocks" ]; then
  filt="$(mktemp)"
  python3 - "$blocks" "$org" "$filt" << 'PY'
import sys
from pathlib import Path
src, org_s, dest = sys.argv[1:]
org = int(org_s, 0)
hi = org + 8192
lines = []
for line in Path(src).read_text().splitlines():
    s = line.strip()
    if not s or s.startswith(";"):
        lines.append(line)
        continue
    parts = s.split()
    start = end = None
    for i, p in enumerate(parts):
        if p == "start" and i + 1 < len(parts):
            start = int(parts[i + 1], 0)
        elif p == "end" and i + 1 < len(parts):
            end = int(parts[i + 1], 0)
    if start is None:
        continue
    if org <= start < hi:
        lines.append(line)
Path(dest).write_text("\n".join(lines) + ("\n" if lines else ""))
PY
  args+=(-b "$filt")
fi

raw="generated/${stem}.raw.asm"
gen="generated/${stem}.generated.asm"

z80dasm "${args[@]}" "$tmpbin" -o "$raw"
rm -f "$tmpbin"
[ -n "${filt:-}" ] && rm -f "$filt"
sed -i '' "s/^	org .*/; (org set by PHASE in ${master_name})/" "$raw"

cp "$raw" "$gen"
python3 "$MSX/strip-listing.py" "$gen"
echo "wrote $gen (clean, fold this)  +  $raw (raw listing, temporary reference)"
