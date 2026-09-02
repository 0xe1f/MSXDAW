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

"""Disassembly progress: leftover INCBIN, auto labels, opcode comments.

  tools/workbench/msx/coverage.py                 # print the report
  tools/workbench/msx/coverage.py --json
  tools/workbench/msx/coverage.py --badges DIR    # Shields.io endpoint JSON
  tools/workbench/msx/coverage.py --readme        # optional local README block

Counts committed source under workbench.cfg (master + source_dir). Layers:
bytes still behind INCBIN, unique z80dasm auto labels left, share of
instruction lines with a ';' comment, and named ``call`` targets preceded
by a comment block.

CI publishes --badges to the orphan ``badges`` branch. README holds static
Shields.io endpoint URLs and is not rewritten each commit.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_LIB = Path(__file__).resolve().parent.parent / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
from game import Game, load  # noqa: E402

BEGIN = "<!-- coverage -->"
END = "<!-- /coverage -->"

AUTO_DEF = re.compile(
    r"^[ \t]*(l[0-9a-fA-F]{4}h|sub_[0-9a-fA-F]{4}h)[ \t]*:",
    re.I | re.M,
)
INCBIN = re.compile(
    r'\bINCBIN[ \t]+"([^"]+)"'
    r"(?:[ \t]*,[ \t]*([^,;\n]+)"
    r"(?:[ \t]*,[ \t]*([^,;\n]+))?)?",
    re.I,
)
# Optional label, then a real Z80 mnemonic (not sjasmplus pseudo-ops).
OPCODE = re.compile(
    r"""^[ \t]*
        (?:[A-Za-z_@.][\w.]*[ \t]*:[ \t]*)?
        (adc|add|and|bit|call|ccf|cp|cpd|cpdr|cpi|cpir|cpl|daa|dec|di|
         djnz|ei|ex|exx|halt|im|in|inc|ind|indr|ini|inir|jp|jr|ld|ldd|
         lddr|ldi|ldir|neg|nop|or|otdr|otir|out|outd|outi|pop|push|res|
         ret|reti|retn|rl|rla|rlc|rlca|rld|rr|rra|rrc|rrca|rrd|rst|sbc|
         scf|set|sla|sll|slia|sra|srl|sub|xor)
        \b
    """,
    re.I | re.X,
)
CALL_TGT = re.compile(
    r"\bcall(?:[ \t]+(?:nz|z|nc|c|po|pe|p|m)[ \t]*,)?[ \t]*"
    r"([A-Za-z_@.][\w.]*)\b",
    re.I,
)
LABEL_DEF = re.compile(r"^([A-Za-z_@.][\w.]*)[ \t]*:")
AUTO_NAME = re.compile(r"^(?:l[0-9a-fA-F]{4}h|sub_[0-9a-fA-F]{4}h)$", re.I)
SKIP_DIR = {".git", "generated", "tools", "gfx", "music", "sfx", "__pycache__"}

WINDOW_BANKS = re.compile(r"^banks_[0-9a-f]+$", re.I)
WINDOW_BANKN = re.compile(r"^(?:bank|seg)\d{2}$", re.I)


def _is_auto_name(name: str) -> bool:
    return bool(AUTO_NAME.match(name))


def _next_is_opcode(lines: list[str], i: int) -> bool:
    """True if this label starts a code routine, not a table / equ."""
    rest = lines[i].split(":", 1)[-1]
    if OPCODE.match(rest):
        return True
    j = i + 1
    while j < len(lines):
        s = lines[j].strip()
        if not s or s.startswith(";"):
            j += 1
            continue
        return bool(OPCODE.match(lines[j]))
    return False


def _preceded_by_docs(lines: list[str], i: int) -> bool:
    """+1 if comment lines with a letter sit immediately above the label."""
    j = i - 1
    while j >= 0 and not lines[j].strip():
        j -= 1
    saw = False
    while j >= 0:
        s = lines[j].strip()
        if not s:
            j -= 1
            continue
        if s.startswith(";"):
            if re.search(r"[A-Za-z]", s[1:]):
                saw = True
            j -= 1
            continue
        break
    return saw


def _int_tok(s: str) -> int:
    s = s.strip().replace("_", "")
    if s.lower().startswith("0x"):
        return int(s, 16)
    if s[-1:] in "hH" and s[:-1]:
        return int(s[:-1], 16)
    return int(s, 0)


def _source_files(game: Game) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()

    def add(p: Path) -> None:
        try:
            r = p.resolve()
        except OSError:
            return
        if r in seen or not p.is_file():
            return
        seen.add(r)
        out.append(p)

    add(game.master_path)
    src = game.source_path
    if src.is_dir():
        for p in sorted(src.rglob("*")):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".asm", ".inc"}:
                continue
            if any(part in SKIP_DIR for part in p.parts):
                continue
            add(p)
    return out


def _window_key(game: Game, path: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(game.source_path.resolve())
    except ValueError:
        return None
    if len(rel.parts) != 1:
        return None
    stem = path.stem
    if WINDOW_BANKS.match(stem) or WINDOW_BANKN.match(stem):
        return stem
    return None


def _incbin_len(game: Game, rel: str, off: str | None, length: str | None) -> int:
    p = (game.root / rel).resolve()
    size = p.stat().st_size if p.is_file() else 0
    if not size:
        name = Path(rel).name
        if re.match(r"^(?:bank|seg)\d{2}\.bin$", name, re.I):
            size = game.bank_size
        else:
            return 0
    o = _int_tok(off) if off and off.strip() else 0
    if length and length.strip():
        return max(0, _int_tok(length))
    return max(0, size - o)


def scan(game: Game) -> dict:
    rom_bytes = game.banks * game.bank_size
    if game.rom_path.is_file():
        rom_bytes = game.rom_path.stat().st_size

    incbin_by_path: dict[str, int] = {}
    auto_global: set[str] = set()
    auto_by_window: dict[str, set[str]] = defaultdict(set)
    incbin_by_window: dict[str, int] = defaultdict(int)
    call_targets: set[str] = set()
    file_lines: list[tuple[Path, str | None, list[str]]] = []
    opcodes = 0
    commented = 0

    for path in _source_files(game):
        text = path.read_text(errors="replace")
        lines = text.splitlines()
        win = _window_key(game, path)
        file_lines.append((path, win, lines))
        for m in AUTO_DEF.finditer(text):
            name = m.group(1).lower()
            auto_global.add(name)
            if win:
                auto_by_window[win].add(name)
        for m in INCBIN.finditer(text):
            n = _incbin_len(game, m.group(1), m.group(2), m.group(3))
            key = m.group(1)
            incbin_by_path[key] = max(incbin_by_path.get(key, 0), n)
            if win:
                incbin_by_window[win] += n
        for line in lines:
            if not OPCODE.match(line):
                continue
            opcodes += 1
            if ";" in line:
                commented += 1
            code = line.split(";", 1)[0]
            for m in CALL_TGT.finditer(code):
                tgt = m.group(1)
                if not _is_auto_name(tgt):
                    call_targets.add(tgt.lower())

    subs = 0
    subs_doc = 0
    subs_by_window: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    seen_subs: set[str] = set()
    for _path, win, lines in file_lines:
        for i, line in enumerate(lines):
            m = LABEL_DEF.match(line)
            if not m:
                continue
            name = m.group(1)
            key = name.lower()
            if _is_auto_name(name) or key not in call_targets:
                continue
            if not _next_is_opcode(lines, i):
                continue
            if key in seen_subs:
                continue
            seen_subs.add(key)
            subs += 1
            doc = _preceded_by_docs(lines, i)
            if doc:
                subs_doc += 1
            if win:
                subs_by_window[win][0] += 1
                if doc:
                    subs_by_window[win][1] += 1

    leftover_disk = 0
    counted_bins: set[Path] = set()
    for rel, n in incbin_by_path.items():
        counted_bins.add((game.root / rel).resolve())
    for i in range(game.banks):
        b = game.leftover_bin(i)
        if b.is_file():
            r = b.resolve()
            if r not in counted_bins:
                leftover_disk += b.stat().st_size

    leftover = sum(incbin_by_path.values()) + leftover_disk
    leftover = min(leftover, rom_bytes)
    labelled = max(0, rom_bytes - leftover)
    pct = round(100.0 * commented / opcodes, 1) if opcodes else 0.0
    subs_pct = round(100.0 * subs_doc / subs, 1) if subs else 0.0

    windows: list[dict] = []
    names = sorted(
        set(auto_by_window) | set(incbin_by_window) | set(subs_by_window)
    )
    for name in names:
        nsub, ndoc = subs_by_window.get(name, [0, 0])
        windows.append(
            {
                "name": name,
                "incbin": incbin_by_window.get(name, 0),
                "auto": len(auto_by_window.get(name, ())),
                "subs": nsub,
                "subs_doc": ndoc,
            }
        )

    return {
        "rom_bytes": rom_bytes,
        "labelled_bytes": labelled,
        "incbin_bytes": leftover,
        "auto_labels": len(auto_global),
        "opcodes": opcodes,
        "commented": commented,
        "comment_pct": pct,
        "subs": subs,
        "subs_doc": subs_doc,
        "subs_pct": subs_pct,
        "windows": windows,
    }


def _kib(n: int) -> str:
    if n % 1024 == 0:
        return str(n // 1024)
    return f"{n / 1024:.1f}"


def _in_source_color(labelled: int, rom: int) -> str:
    if rom <= 0:
        return "lightgrey"
    if labelled >= rom:
        return "brightgreen"
    if labelled * 2 >= rom:
        return "yellow"
    return "orange"


def _named_color(n: int) -> str:
    if n == 0:
        return "brightgreen"
    if n <= 50:
        return "yellow"
    if n <= 200:
        return "orange"
    return "red"


def _comment_color(pct: float) -> str:
    if pct >= 50:
        return "brightgreen"
    if pct >= 20:
        return "yellow"
    if pct >= 5:
        return "orange"
    return "lightgrey"


def shields_endpoint(label: str, message: str, color: str) -> dict:
    return {
        "schemaVersion": 1,
        "label": label,
        "message": message,
        "color": color,
        "cacheSeconds": 300,
    }


def badge_payloads(stats: dict) -> dict[str, dict]:
    rom = stats["rom_bytes"]
    lab = stats["labelled_bytes"]
    auto = stats["auto_labels"]
    pct = stats["comment_pct"]
    return {
        "in-source.json": shields_endpoint(
            "in source", f"{_kib(lab)} / {_kib(rom)} KiB", _in_source_color(lab, rom)
        ),
        "named.json": shields_endpoint(
            "named", f"{auto} left", _named_color(auto)
        ),
        "op-comments.json": shields_endpoint(
            "op comments", f"{pct:g}%", _comment_color(pct)
        ),
        "sub-comments.json": shields_endpoint(
            "sub comments",
            f"{stats['subs_doc']} / {stats['subs']}",
            _comment_color(stats["subs_pct"]),
        ),
    }


def write_badges(dest: Path, stats: dict) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "coverage.json").write_text(json.dumps(stats, indent=2) + "\n")
    (dest / "coverage.md").write_text(render(stats))
    for name, payload in badge_payloads(stats).items():
        (dest / name).write_text(json.dumps(payload, indent=2) + "\n")


def render(stats: dict) -> str:
    rom_k = _kib(stats["rom_bytes"])
    lab_k = _kib(stats["labelled_bytes"])
    lines = [
        f"In source: {lab_k} / {rom_k} KiB labelled `.asm`",
        f"Named: {stats['auto_labels']} auto labels left",
        f"Op comments: {stats['comment_pct']:g}% of opcode lines",
        f"Sub comments: {stats['subs_doc']} / {stats['subs']} preceded by docs",
    ]
    rows = [
        w
        for w in stats["windows"]
        if w["incbin"] > 0
        or w["auto"] > 0
        or (w.get("subs", 0) and w.get("subs_doc", 0) < w["subs"])
    ]
    if rows:
        lines.append("")
        lines.append("| Window | INCBIN | Auto left | Sub comments |")
        lines.append("|---|---|---|---|")
        for w in rows:
            inc = f"{_kib(w['incbin'])} KiB" if w["incbin"] else "—"
            auto = w["auto"] or "—"
            nsub = w.get("subs", 0)
            subs = f"{w.get('subs_doc', 0)} / {nsub}" if nsub else "—"
            lines.append(f"| `{w['name']}` | {inc} | {auto} | {subs} |")
    return "\n".join(lines) + "\n"


def write_readme(readme: Path, body: str) -> None:
    block = f"{BEGIN}\n{body.rstrip()}\n\n{END}\n"
    if readme.is_file():
        text = readme.read_text()
    else:
        text = ""
    if BEGIN in text and END in text:
        pre, rest = text.split(BEGIN, 1)
        _, post = rest.split(END, 1)
        if post.startswith("\n"):
            post = post[1:]
        readme.write_text(pre + block + post)
        return
    lines = text.splitlines(keepends=True)
    insert_at = 0
    if lines and lines[0].startswith("# "):
        insert_at = 1
        while insert_at < len(lines) and (
            lines[insert_at].startswith("[![")
            or lines[insert_at].startswith("![")
            or lines[insert_at].strip() == ""
        ):
            insert_at += 1
    new = "".join(lines[:insert_at])
    if insert_at and (not new.endswith("\n\n")):
        if not new.endswith("\n"):
            new += "\n"
        new += "\n"
    new += block + "\n" + "".join(lines[insert_at:])
    readme.write_text(new)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--badges",
        metavar="DIR",
        help="write Shields.io endpoint JSON (and coverage.md) here",
    )
    ap.add_argument(
        "--readme",
        nargs="?",
        const="README.md",
        metavar="PATH",
        help="optional: write a <!-- coverage --> block (offline / no GitHub)",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    game = load()
    stats = scan(game)
    body = render(stats)
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        sys.stdout.write(body)
    if args.badges:
        dest = Path(args.badges)
        if not dest.is_absolute():
            dest = game.root / dest
        write_badges(dest, stats)
    if args.readme:
        path = Path(args.readme)
        if not path.is_absolute():
            path = game.root / path
        write_readme(path, body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
