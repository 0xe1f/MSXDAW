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

"""Locate an MSXDAW game repo and read workbench.cfg.

Walks up from cwd (or GAME=) looking for workbench.cfg. Do not assume a
fixed number of parents — tools live inside the tools/workbench submodule.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

CFG_NAME = "workbench.cfg"
MAPPER_ORG = {
    # Default CPU window per 8 KiB bank index, repeating across the four
    # mapper pages. Games override with bank_org= in workbench.cfg.
    "konami4": [0x4000, 0x6000, 0x8000, 0xA000],
    "konami-scc": [0x4000, 0x6000, 0x8000, 0xA000],
    "ascii8": [0x4000, 0x6000, 0x8000, 0xA000],
    "ascii16": [0x4000, 0x6000, 0x8000, 0xA000],
    "linear": [0x4000, 0x6000, 0x8000, 0xA000],
}


class Game:
    def __init__(self, root: Path, cfg: dict[str, str]):
        self.root = root
        self.cfg = cfg
        self.name = cfg.get("name", root.name)
        self.master = cfg.get("master", f"{self.name}.asm")
        self.rom_name = cfg.get("rom", f"{self.name}.rom")
        self.mapper = cfg.get("mapper", "konami4")
        self.banks = int(cfg.get("banks", "16"), 0)
        self.bank_size = int(cfg.get("bank_size", "8192"), 0)
        self.source_dir = cfg.get("source_dir", "banks")
        self.bank_prefix = cfg.get("bank_prefix", "bank")
        self.sym = cfg.get("sym", f"{self.source_dir}/msx.sym")
        scan = cfg.get("scan_banks", "0,1,2,3")
        self.scan_banks = [int(x, 0) for x in scan.split(",") if x.strip()]
        self.migrated = cfg.get("migrated", "").strip().lower()
        self._org = self._parse_org(cfg)

    def is_migrated(self, bank: int) -> bool:
        if self.migrated in ("all", "*"):
            return True
        if self.migrated:
            nums = {int(x, 0) for x in self.migrated.replace(",", " ").split() if x}
            if bank in nums:
                return True
        return (self.source_path / f"{self.bank_stem(bank)}.asm").is_file()

    def _parse_org(self, cfg: dict[str, str]) -> list[int]:
        raw = cfg.get("bank_org", "")
        if raw:
            return [int(x, 16) if not x.lower().startswith("0x") else int(x, 0)
                    for x in raw.replace(",", " ").split()]
        cycle = MAPPER_ORG.get(self.mapper, MAPPER_ORG["konami4"])
        return [cycle[i % len(cycle)] for i in range(self.banks)]

    def bank_org(self, bank: int) -> int:
        if bank < 0 or bank >= self.banks:
            raise IndexError(f"bank {bank} out of range 0..{self.banks - 1}")
        if bank < len(self._org):
            return self._org[bank]
        cycle = MAPPER_ORG.get(self.mapper, MAPPER_ORG["konami4"])
        return cycle[bank % len(cycle)]

    @property
    def rom_path(self) -> Path:
        env = os.environ.get("ROM")
        if env:
            p = Path(env)
            return p if p.is_absolute() else self.root / p
        return self.root / self.rom_name

    @property
    def master_path(self) -> Path:
        return self.root / self.master

    @property
    def source_path(self) -> Path:
        return self.root / self.source_dir

    @property
    def sym_path(self) -> Path:
        return self.root / self.sym

    @property
    def generated(self) -> Path:
        return self.root / "generated"

    @property
    def sjasm(self) -> Path:
        return self.root / "tools" / "sjasmplus"

    def bank_stem(self, bank: int) -> str:
        return f"{self.bank_prefix}{bank:02d}"

    def leftover_bin(self, bank: int) -> Path:
        return self.source_path / f"{self.bank_stem(bank)}.bin"


def parse_cfg(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def find_root(start: Path | None = None) -> Path | None:
    env = os.environ.get("GAME")
    if env:
        p = Path(env).expanduser().resolve()
        if (p / CFG_NAME).is_file():
            return p
        if p.is_file() and p.name == CFG_NAME:
            return p.parent
    cur = (start or Path.cwd()).resolve()
    for d in [cur, *cur.parents]:
        if (d / CFG_NAME).is_file():
            return d
    return None


def load(start: Path | None = None) -> Game:
    root = find_root(start)
    if root is None:
        sys.exit("no workbench.cfg found (cwd walk, or set GAME=)")
    return Game(root, parse_cfg(root / CFG_NAME))


def daw_root() -> Path:
    """This file lives at msxdaw/lib/game.py (or tools/workbench/lib/game.py)."""
    return Path(__file__).resolve().parent.parent


def python_paths() -> list[str]:
    root = daw_root()
    return [str(root / "msx"), str(root / "konami"), str(root / "lib")]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", action="store_true", help="print game repo root")
    p.add_argument("--rom", action="store_true", help="print ROM path")
    p.add_argument("--master", action="store_true", help="print master asm path")
    p.add_argument("--daw", action="store_true", help="print MSXDAW / workbench root")
    p.add_argument("--get", metavar="KEY", help="print a cfg value")
    p.add_argument("--bank-org", type=int, metavar="N", help="print CPU origin for bank N")
    args = p.parse_args(argv)
    if args.daw:
        print(daw_root())
        return 0
    g = load()
    if args.root:
        print(g.root)
    elif args.rom:
        print(g.rom_path)
    elif args.master:
        print(g.master_path)
    elif args.get:
        print(g.cfg.get(args.get, ""))
    elif args.bank_org is not None:
        print(f"0x{g.bank_org(args.bank_org):04X}")
    else:
        print(g.root)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
