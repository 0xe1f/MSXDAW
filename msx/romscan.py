#!/usr/bin/env python3
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

"""Static xref and dispatch-table decode for banked Z80 ROMs.

  xref  - real control-transfers (call/jp/jr/djnz) vs bare little-endian words
  table - decode a jump/handler table (byte or word), with optional index base

Default scan set and per-bank CPU origins come from workbench.cfg.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent.parent / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
from game import load  # noqa: E402

ABS_OPS = {0xC3: "jp", 0xCD: "call",
           0xC2: "jp nz", 0xCA: "jp z", 0xD2: "jp nc", 0xDA: "jp c",
           0xE2: "jp po", 0xEA: "jp pe", 0xF2: "jp p", 0xFA: "jp m"}
REL_OPS = {0x18: "jr", 0x20: "jr nz", 0x28: "jr z", 0x30: "jr nc",
           0x38: "jr c", 0x10: "djnz"}


def load_rom(path=None):
    g = load()
    p = Path(path) if path else g.rom_path
    if not p.is_file():
        sys.exit(f"no ROM at {p} (run make, or set ROM=)")
    return g, p.read_bytes()


def bank_bytes(g, rom, bank):
    off = bank * g.bank_size
    if off + g.bank_size > len(rom):
        sys.exit(f"bank {bank} out of range for {len(rom)}-byte ROM")
    return rom[off:off + g.bank_size]


def parse_int(s):
    return int(s, 0)


def cmd_xref(args):
    g, rom = load_rom(args.rom)
    target = parse_int(args.addr)
    banks = [int(x) for x in args.banks.split(",")] if args.banks else g.scan_banks
    lo, hi = target & 0xFF, target >> 8
    found = 0
    for bank in banks:
        data = bank_bytes(g, rom, bank)
        base = args.base if args.base is not None else g.bank_org(bank)
        hits = []
        for i in range(len(data) - 2):
            op = data[i]
            if op in ABS_OPS and data[i + 1] == lo and data[i + 2] == hi:
                hits.append((base + i, f"{ABS_OPS[op]} {target:#06x}", "code"))
        if base <= target < base + g.bank_size:
            for i in range(len(data) - 1):
                op = data[i]
                if op in REL_OPS:
                    disp = data[i + 1] - 256 if data[i + 1] > 127 else data[i + 1]
                    if base + i + 2 + disp == target:
                        hits.append((base + i, f"{REL_OPS[op]} {target:#06x}", "code"))
        for i in range(len(data) - 1):
            if data[i] == lo and data[i + 1] == hi:
                if not (i >= 1 and data[i - 1] in ABS_OPS):
                    hits.append((base + i, f"word {target:#06x}", "data?"))
        for addr, desc, kind in sorted(hits):
            print(f"  bank{bank:<2} {addr:#06x}  [{kind:5}] {desc}")
            found += 1
    if not found:
        print("  (no references found)")
    else:
        print(f"\n{found} reference(s). 'code' = real transfer; "
              "'data?' = word match (verify: may be a pointer table or coincidence).")


def cmd_table(args):
    g, rom = load_rom(args.rom)
    addr = parse_int(args.addr)
    if args.bank is not None:
        bank = args.bank
    else:
        bank = next((i for i in range(g.banks) if g.bank_org(i) == (addr & 0xE000)), 0)
    data = bank_bytes(g, rom, bank)
    base = args.base if args.base is not None else g.bank_org(bank)
    off = addr - base
    if not (0 <= off < g.bank_size):
        sys.exit(f"addr {addr:#06x} not inside bank{bank} ({base:#06x}..)")
    n = parse_int(str(args.words if args.words is not None else args.bytes))
    width = 2 if args.words is not None else 1
    idx_base = args.index_base
    print(f"table @ {addr:#06x} (bank{bank}), {n} x {width}-byte"
          + (f", index+{idx_base}" if idx_base else "") + ":")
    for k in range(n):
        e = off + k * width
        if width == 2:
            val = data[e] | (data[e + 1] << 8)
            print(f"  [{k + idx_base:#04x}] -> {val:#06x}")
        else:
            print(f"  [{k + idx_base:#04x}] = {data[e]:#04x} ({data[e]})")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", help="ROM image (default: $ROM, then workbench.cfg rom=)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    x = sub.add_parser("xref", help="find references to an address")
    x.add_argument("addr")
    x.add_argument("--banks", "--segs", dest="banks",
                   help="comma list of banks to scan (default: cfg scan_banks)")
    x.add_argument("--base", type=parse_int, help="override CPU base for listed banks")
    x.set_defaults(func=cmd_xref)

    t = sub.add_parser("table", help="decode a dispatch/jump table")
    t.add_argument("addr")
    g = t.add_mutually_exclusive_group(required=True)
    g.add_argument("--words", help="decode N little-endian word entries")
    g.add_argument("--bytes", help="decode N byte entries")
    t.add_argument("--bank", "--seg", dest="bank", type=int, help="bank index")
    t.add_argument("--base", type=parse_int, help="override base addr")
    t.add_argument("--index-base", type=parse_int, default=0,
                   help="starting index label (e.g. 1 if dispatcher does dec a)")
    t.set_defaults(func=cmd_table)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
