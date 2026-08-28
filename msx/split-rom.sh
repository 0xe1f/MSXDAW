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

# Extract leftover 8 KiB banks from the ROM, and delete bins that have
# already graduated to source.
#
#   split-rom.sh
#
# A bank whose .asm exists (banks/bankNN.asm or source_dir matching prefix)
# is treated as migrated: its .bin is removed. Otherwise the ROM slice is
# written so the master can INCBIN it.
set -euo pipefail
MSX="$(cd "$(dirname "$0")" && pwd)"
DAW="$(cd "$MSX/.." && pwd)"
export PYTHONPATH="${DAW}/lib${PYTHONPATH:+:$PYTHONPATH}"
cd "$(python3 "$DAW/lib/game.py" --root)"

python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, '${DAW}/lib')
from game import load
g = load()
g.source_path.mkdir(parents=True, exist_ok=True)
rom_path = g.rom_path
rom = rom_path.read_bytes() if rom_path.is_file() else None
migrated = 0
extracted = 0
for n in range(g.banks):
    stem = g.bank_stem(n)
    asm = g.source_path / f'{stem}.asm'
    binp = g.leftover_bin(n)
    if g.is_migrated(n):
        if binp.exists():
            binp.unlink()
        migrated += 1
        continue
    if rom is None:
        continue
    off = n * g.bank_size
    binp.write_bytes(rom[off:off + g.bank_size])
    extracted += 1
print(f'migrated {migrated} banks (no leftover .bin); extracted {extracted} leftover bins')
if rom is None and extracted == 0 and migrated < g.banks:
    print('no ROM at', rom_path, '(set ROM= or run make) — leftover bins not refreshed', file=sys.stderr)
"
