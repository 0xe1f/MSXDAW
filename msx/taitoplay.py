#!/usr/bin/env python3
# Copyright 2026 Akop Karapetyan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Render Taito PSG bytecode (Arkanoid-style) through an AY-3-8910 model.

Reimplements psg_play / psg_tick: a 28-byte index at page 0xB4, 5-byte
records, two 22-byte slots, and an 8-op fetch (bit7=1). Not Konami
packed-PSG — do not point konami/psgplay.py at these streams.

AY generators are the shared CocoaMSX ``AY8910.c`` model in konami.psgplay.
Volume envelopes are multi-segment: when a slide's rest count hits 0,
psg_tick jumps to lb807h for the next env byte.
Slot0 period ops (8xh) fall through to that env path, so each bass note
re-attacks; a pitch-only write leaves later notes stuck at the held vol.

Usage:
  tools/workbench/msx/taitoplay.py Game.rom --id 0xC3
  tools/workbench/msx/taitoplay.py Game.rom --sfx --id 0x05
"""
from __future__ import annotations

import argparse
import os
import sys

_KONAMI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "konami")
sys.path.insert(0, _KONAMI)
from psgplay import AY, FRAME_HZ, write_wav  # noqa: E402

CPU_BASE = 0x4000
RAM_BASE = 0xE5C0
RAM_SIZE = 0x40
PSG_PAGE = 0xB400
SLOT0 = 0xE5D3
SLOT1 = 0xE5E9
IDX0 = 0xB406  # hdr_idx; play offsets 6..33 land here


class Driver:
    """Taito psg_play / psg_tick over a linear 32 KiB window."""

    def __init__(self, rom: bytes, cpu_base: int = CPU_BASE):
        self.rom = rom
        self.cpu_base = cpu_base
        self.ram = bytearray(RAM_SIZE)
        self.ay: AY | None = None
        self.ix = SLOT0
        self.bc = 0
        self.loop_hits = 0
        self.reset()

    def reset(self) -> None:
        self.ram[:] = bytes(RAM_SIZE)
        # cart_init zeros E5C2; F8 later writes 1. Force enable.
        self.wb(0xE5C2, 1)
        self.wb(0xE5C3, 0xFF)
        self.wb(0xE5CB, 0xBF)
        self.loop_hits = 0

    def peek(self, cpu: int) -> int:
        cpu &= 0xFFFF
        off = cpu - self.cpu_base
        if off < 0 or off >= len(self.rom):
            return 0
        return self.rom[off]

    def peek16(self, cpu: int) -> int:
        return self.peek(cpu) | (self.peek((cpu + 1) & 0xFFFF) << 8)

    def rb(self, addr: int) -> int:
        return self.ram[addr - RAM_BASE]

    def wb(self, addr: int, val: int) -> None:
        self.ram[addr - RAM_BASE] = val & 0xFF

    def rw(self, addr: int) -> int:
        return self.rb(addr) | (self.rb(addr + 1) << 8)

    def ww(self, addr: int, val: int) -> None:
        self.wb(addr, val)
        self.wb(addr + 1, val >> 8)

    def slot_active(self, slot: int) -> bool:
        return self.rb(slot) != 0

    def dirty(self, mask: int) -> None:
        self.wb(0xE5C3, self.rb(0xE5C3) | mask)

    def play(self, sid: int) -> None:
        self.wb(0xE5C0, sid & 0xFF)
        self._psg_play()

    def _psg_play(self) -> None:
        a = self.rb(0xE5C0)
        if a < 0x80:
            self._install(SLOT0, (a + 6) & 0xFF)
            return
        if a < 0xC0:
            self._install(SLOT1, (a + 0x90) & 0xFF)
            return
        a = (a - 0xF0) & 0xFF
        if a <= 0x0F and self.rb(0xE5C0) >= 0xF0:
            self._control(self.rb(0xE5C0) - 0xF0)
            return
        # pair: sub 0xF0 borrowed, then +0x30, *2, +0x10
        a = self.rb(0xE5C0)
        a = (a - 0xF0) & 0xFF
        a = (a + 0x30) & 0xFF
        a = (a + a) & 0xFF
        a = (a + 0x10) & 0xFF
        self._install(SLOT0, a)
        self._install(SLOT1, (a + 1) & 0xFF)

    def _control(self, n: int) -> None:
        # lb559h. F8 (n=8) rrca/rra/rrca → writes 1 to E5C2.
        a = n & 0xFF
        if a & 1:
            return
        a >>= 1
        if a & 1:
            self.wb(0xE5C1, a)
            self.wb(0xE5CB, self.rb(0xE5CB) | 0x80)
            return
        a >>= 1
        self.wb(0xE5C2, a)

    def _install(self, slot: int, off: int) -> None:
        # sub_b51dh: A is a 0xB4xx offset; that byte is the record low addr.
        rec_lo = self.peek(PSG_PAGE | (off & 0xFF))
        rec = PSG_PAGE | rec_lo
        if self.rb(0xE5C2) == 0:
            return
        was = self.rb(slot)
        self.wb(slot, 1)
        hl = slot + 1
        if was:
            pri = self.peek(rec) & 0xF0
            if pri < self.rb(hl):
                self.wb(slot, was)
                return
        d = self.peek(rec) & 0x0F
        e = self.peek(rec + 1)
        rec2 = rec + 2
        self.wb(hl, self.peek(rec2) & 0xF0)
        self.wb(hl + 1, e)
        self.wb(hl + 2, d)
        hl = slot + 4
        self.wb(hl, self.peek(rec2) & 0x0F)
        self.ww(hl + 1, rec2)
        stream = self.peek16(rec + 3)
        self.ww(slot + 7, stream)
        self.wb(slot + 9, 1)

    def _b4b5(self, slot: int) -> tuple[bool, int]:
        """Duration / loop. Returns (carry, A). NC = no fetch this frame."""
        if self.rb(slot) == 0:
            return False, 0
        dur = self.rb(slot + 9)
        dur = (dur - 1) & 0xFF
        self.wb(slot + 9, dur)
        if dur:
            return False, 0
        a = self.peek(self.bc)
        if a:
            return True, a
        # *BC == 0: inner loop at slot+4, else outer at slot+3, else stop.
        a = self.rb(slot + 2)
        inner = (self.rb(slot + 4) - 1) & 0xFF
        self.wb(slot + 4, inner)
        if inner:
            self.loop_hits += 1
            rec2 = self.rw(slot + 5)
            self.bc = rec2
            self._reload_stream(slot, rec2)
            return False, 0
        outer = (self.rb(slot + 3) - 1) & 0xFF
        self.wb(slot + 3, outer)
        if outer:
            rec2 = self.rw(slot + 5)
            self.bc = (rec2 + 3) & 0xFFFF
            self.wb(slot + 4, self.peek(rec2) & 0x0F)
            self.ww(slot + 5, rec2)
            self._reload_stream(slot, rec2)
            return False, 0
        self.wb(slot, 0)
        self.wb(0xE5C0, a)
        self._psg_play()
        return False, 0

    def _reload_stream(self, slot: int, rec2: int) -> None:
        # lb54dh from BC pointing at rec[2]
        self.bc = (rec2 + 1) & 0xFFFF
        lo = self.peek(self.bc)
        self.bc = (self.bc + 1) & 0xFFFF
        hi = self.peek(self.bc)
        self.ww(slot + 7, lo | (hi << 8))
        self.wb(slot + 9, 1)

    def _fetch_ops(self, slot: int, op1: bool) -> None:
        self.ix = slot
        for _ in range(256):
            self.bc = (self.bc + 1) & 0xFFFF
            a = self.peek(self.bc)
            if a & 0x80 == 0:
                return
            op = (a >> 4) & 7
            e = a & 0x0F
            if op1:
                self._op1(op, e)
            else:
                self._op0(op, e)

    def tick(self) -> None:
        if self.rb(0xE5C1):
            return
        self._flush()
        self.wb(0xE5C3, 0)

        self.bc = self.rw(0xE5DA)
        cy, a = self._b4b5(SLOT0)
        if cy:
            self.wb(0xE5DC, a)
            self._fetch_ops(SLOT0, False)
            self.ww(0xE5DA, self.bc)

        self.bc = self.rw(0xE5F0)
        cy, a = self._b4b5(SLOT1)
        if cy:
            self.wb(0xE5F2, a)
            self._fetch_ops(SLOT1, True)
            self.ww(0xE5F0, self.bc)

        bc = self.rw(0xE5C4)
        bc = self._slide_period(0xE5DE, bc, 0x01)
        self.ww(0xE5C4, bc)
        vol_a = self._slide_vol(0xE5E1, self.rb(0xE5CC), 0x10)
        vol_a = self._decay_a(vol_a)
        self.wb(0xE5CC, vol_a)

        bc = self.rw(0xE5C6)
        bc = self._slide_period(0xE5F4, bc, 0x02)
        self.ww(0xE5C6, bc)
        vol_c = self._slide_vol(0xE5F7, self.rb(0xE5CE), 0x40)
        self.wb(0xE5CE, vol_c)

    def _flush(self) -> None:
        assert self.ay is not None
        dirty = self.rb(0xE5C3)
        # Periods / noise / vols are safe to rewrite every frame.
        for i, addr in enumerate(range(0xE5C4, 0xE5CB)):
            self.ay.write(i, self.rb(addr))
        mix = self.rb(0xE5CB)
        if mix & 0x80:
            io = self.ay.reg[7] & 0xC0
            self.ay.write(7, io | (mix & 0x3F))
        for i, addr in enumerate(range(0xE5CC, 0xE5CF)):
            self.ay.write(8 + i, self.rb(addr))
        self.ay.write(11, self.rb(0xE5CF))
        self.ay.write(12, self.rb(0xE5D0))
        if (dirty & 0x80) or (self.rb(0xE5D2) & 0x08):
            self.ay.write(13, self.rb(0xE5D1))
            self.wb(0xE5D2, self.rb(0xE5D2) & 0xF7)

    def _set_period(self, hl_hi: int, d: int, e: int) -> None:
        # sub_b6e6h
        a = self.rb(self.ix + 0x0B) & 7
        self.wb(self.ix + 0x0C, a)
        if self.rb(self.ix + 0x0B) & 0x40:
            a = self.rb(self.ix + 0x0D)
            if a & 0x80:
                self.wb(self.ix + 0x0D, (-a) & 0xFF)
        self.wb(hl_hi, e)
        self.bc = (self.bc + 1) & 0xFFFF
        self.wb(hl_hi - 1, self.peek(self.bc))
        flags = self.rb(0xE5D2)
        if flags & d:
            self.wb(0xE5D2, flags | 0x08)
        self.dirty(d)

    def _mixer(self, d: int, e: int, opcode: int) -> bool:
        """sub_b82d / sub_b831. False = skip the rest of this handler."""
        self.wb(self.ix + 0x0B, 0)
        l = self.rb(0xE5CB)
        a = e
        if opcode & 1:
            a = (~a) & 0xFF
            l = a & l
        else:
            l = (a | l) & 0xFF
        a = d
        if opcode & 2:
            a = (~a) & 0xFF
            l = a & l
        else:
            l = (a | l) & 0xFF
        self.wb(0xE5CB, l | 0x80)
        # Third srl of rrca(opcode): opcode bit2. NC → pop handler, keep fetching.
        return (opcode & 4) != 0

    def _env_vol(self, idx_addr: int) -> int:
        """sub_b7e6h. Returns volume nibble in E (0 if idx is 0)."""
        idx = self.rb(idx_addr)
        if idx == 0:
            return 0
        ptr = 0xB4AE + idx
        entry = self.peek(ptr)
        src = 0xB400 | entry
        raw = self.peek(src)
        self.wb(idx_addr - 1, raw & 0x70)
        self.wb(idx_addr - 2, entry)
        if raw & 0x80:
            vol = raw & 0x0F
            self._env_setup(idx_addr - 2, src)
            return vol
        self._env_setup(idx_addr - 2, src)
        return raw & 0x0F

    def _env_setup(self, hl_ptr: int, src: int) -> None:
        # lb807h; HL on entry is the stored pointer byte (idx_addr-2).
        p = (self.rb(hl_ptr) + 1) & 0xFF
        self.wb(hl_ptr, p)
        e = self.peek(0xB400 | p)
        self.wb(hl_ptr - 1, 1)
        d = ((e & 0xC0) | 0x80) >> 1  # scf; rra on (e&C0)
        # Z80: A=(e&C0); scf; rra → bit7=1, rest = (e&C0)>>1
        d = 0x80 | ((e & 0xC0) >> 1)
        a = e
        if d != 0xE0:
            n = ((e & 0x78) >> 3) + 1
            self.wb(hl_ptr - 1, n)
            a = e & 7
        a = (a & 0x3F) + 1
        self.wb(hl_ptr - 2, a)
        self.wb(hl_ptr - 3, a | d)

    def _slide_period(self, hl: int, bc: int, d: int) -> int:
        e = self.rb(hl)
        if e & 0x80 == 0:
            return bc
        n = (self.rb(hl + 1) - 1) & 0xFF
        self.wb(hl + 1, n)
        if n:
            return bc
        self.wb(hl + 1, e & 7)
        a = self.rb(hl + 2)
        if e & 0x40:
            a = (-a) & 0xFF
            self.wb(hl + 2, a)
        if a & 0x80:
            delta = a - 256
        else:
            delta = a
        bc = (bc + delta) & 0xFFFF
        self.dirty(d)
        return bc

    def _slide_vol(self, hl: int, vol: int, d: int) -> int:
        b = self.rb(hl)
        if b & 0x80 == 0:
            return vol
        n = (self.rb(hl + 1) - 1) & 0xFF
        self.wb(hl + 1, n)
        if n:
            return vol
        self.wb(hl + 1, b & 0x0F)
        c = vol
        rest = (self.rb(hl + 2) - 1) & 0xFF
        self.wb(hl + 2, rest)
        if rest:
            if b & 0x40:
                c = min(c + 2, 0x0F)
            else:
                if c:
                    c -= 1
            self.dirty(d)
            return c
        # +4 is the remaining-segment counter (first env byte & 0x70).
        # add 0F0h; NZ → lb807h (next env byte at the pointer in +3).
        v = (self.rb(hl + 4) + 0xF0) & 0xFF
        self.wb(hl + 4, v)
        if v:
            self._env_setup(hl + 3, 0)
            return c
        self.wb(hl, 0)
        return c

    def _decay_a(self, vol: int) -> int:
        a = self.rb(0xE5E7)
        if a & 0x80 == 0:
            return vol
        n = (self.rb(0xE5E8) - 1) & 0xFF
        self.wb(0xE5E8, n)
        if n:
            return vol
        self.wb(0xE5E8, a & 0x1F)
        if vol:
            vol -= 1
            self.dirty(0x10)
            return vol
        self.wb(0xE5E7, a & 0x1F)
        self.dirty(0x10)
        return vol

    # --- opcode tables (psg_op0 / psg_op1) ---

    def _op0(self, op: int, e: int) -> None:
        opcode = self.peek(self.bc)
        if op == 0:
            self._set_period(0xE5C5, 0x01, e)
            # psg_op_fn falls through into lb67eh: period A retriggers env.
            # idx 0: sub_b7e6h pops without writing vol, so leave E5CC.
            if self.rb(0xE5E6):
                vol = self._env_vol(0xE5E6)
                a = self.rb(0xE5E7) & 0x1F
                if a:
                    self.wb(0xE5E7, self.rb(0xE5E7) | 0x80)
                    self.wb(0xE5E8, a)
                self.wb(0xE5CC, vol)
                self.dirty(0x10)
        elif op == 1:
            a = self.rb(0xE5E7) & 0x1F
            if a:
                self.wb(0xE5E7, self.rb(0xE5E7) | 0x80)
                self.wb(0xE5E8, a)
            self.wb(0xE5CC, e)
            self.dirty(0x10)
        elif op == 2:
            if e & 0x08:
                if not self._mixer(0x08, 0x01, opcode):
                    return
                self.wb(0xE5E7, 0)
                self.wb(0xE5E6, 0)
                self.wb(0xE5E1, 0)
                self.wb(0xE5CC, e)
                self.dirty(0x10)
            else:
                self._pitch_env(0xE5DE, e)
        elif op == 3:
            self.wb(0xE5E6, e)
            if e:
                vol = self._env_vol(0xE5E6)
                a = self.rb(0xE5E7) & 0x1F
                if a:
                    self.wb(0xE5E7, self.rb(0xE5E7) | 0x80)
                    self.wb(0xE5E8, a)
                self.wb(0xE5CC, vol)
                self.dirty(0x10)
            else:
                self.wb(0xE5E1, 0)
        elif op == 4:
            self.wb(0xE5E8, e | 0x10)
            self.wb(0xE5E7, e | 0x90)
        elif op == 5:
            self.wb(0xE5E8, e | 0x10)
            self.wb(0xE5E7, e | 0x90)
        elif op == 6:
            self.wb(0xE5CA, e)
            self.dirty(0x08)
        else:
            self.wb(0xE5CA, e | 0x10)
            self.dirty(0x08)

    def _op1(self, op: int, e: int) -> None:
        opcode = self.peek(self.bc)
        if op == 0:
            self._set_period(0xE5C7, 0x02, e)
        elif op == 1:
            # B71D: ld d,20h / ld a,e / ld (E5CD),a  — nibble is vol B
            self.wb(0xE5CD, e)
            self.dirty(0x20)
        elif op == 2:
            if e & 0x08:
                if not self._mixer(0x10, 0x02, opcode):
                    return
                # mixer leaves E=10h (AY envelope on B)
                self.wb(0xE5CD, 0x10)
                self.dirty(0x20)
            else:
                self._pitch_env(0xE5F4, e)
        elif op == 3:
            if e & 0x08:
                self.wb(0xE5D1, e)
                self.bc = (self.bc + 1) & 0xFFFF
                self.wb(0xE5CF, self.peek(self.bc))
                self.bc = (self.bc + 1) & 0xFFFF
                self.wb(0xE5D0, self.peek(self.bc))
                self.dirty(0x80)
            else:
                self.wb(0xE5D2, (e << 1) & 0xFF)
        elif op == 4:
            self.wb(0xE5CF, (e << 4) & 0xFF)
            self.bc = (self.bc + 1) & 0xFFFF
            self.wb(0xE5D0, self.peek(self.bc))
            self.dirty(0x80)
        elif op == 5:
            self._set_period(0xE5C9, 0x04, e)
            vol = self._env_vol(0xE5FC)
            self.wb(0xE5CE, vol)
            self.dirty(0x40)
        elif op == 6:
            self.wb(0xE5CE, e)
            self.dirty(0x40)
        else:
            if e & 0x08:
                if not self._mixer(0x20, 0x04, opcode):
                    return
                self.wb(0xE5FC, 0)
                self.wb(0xE5F7, 0)
                self.wb(0xE5CE, e)
                self.dirty(0x40)
            else:
                self.wb(0xE5FC, e)
                if e:
                    vol = self._env_vol(0xE5FC)
                    self.wb(0xE5CE, vol)
                    self.dirty(0x40)
                else:
                    self.wb(0xE5F7, 0)

    def _pitch_env(self, hl: int, e: int) -> None:
        self.wb(hl, e)
        if e == 0:
            return
        self.wb(hl, e | 0x80)
        self.bc = (self.bc + 1) & 0xFFFF
        raw = self.peek(self.bc)
        rot = ((raw << 1) | (raw >> 7)) & 0xFF
        if rot & 0x80:
            a = ((rot >> 1) | 0x80) & 0xFF
        else:
            a = rot >> 1
        # jr c after sra: carry is original bit7 (bit0 of rlca).
        if raw & 0x80 == 0:
            a = raw
            self.wb(hl, self.rb(hl) | 0x40)
        self.wb(hl + 1, e)
        self.wb(hl + 2, a)

    def alive(self) -> bool:
        return self.slot_active(SLOT0) or self.slot_active(SLOT1)

    def render(
        self,
        sid: int,
        sample_rate: int,
        *,
        sfx: bool = False,
        loops: int = 8,
        min_seconds: float = 20.0,
        seconds: float | None = None,
    ) -> bytes:
        self.reset()
        self.ay = AY(sample_rate)
        self.ay.write(7, 0xBF)
        self.play(sid)
        cap = (4.0 if sfx else 90.0) if seconds is None else seconds
        spf = int(round(sample_rate / FRAME_HZ))
        max_frames = int(cap * FRAME_HZ)
        fade_frames = max(1, int((0.12 if sfx else 1.0) * FRAME_HZ))
        pcm = bytearray()
        stop_at = None
        silent = 0
        for frame in range(max_frames + fade_frames + 1):
            self.tick()
            if stop_at is None:
                if not self.alive():
                    silent += 1
                    if silent >= 2 or frame >= max_frames:
                        stop_at = frame + fade_frames
                else:
                    silent = 0
                    if (
                        not sfx
                        and self.loop_hits >= loops
                        and frame > int(min_seconds * FRAME_HZ)
                    ):
                        stop_at = frame + fade_frames
                    elif frame >= max_frames:
                        stop_at = frame + fade_frames
            gain = 1.0
            if stop_at is not None:
                left = stop_at - frame
                if left <= 0:
                    break
                if left < fade_frames:
                    gain = left / fade_frames
            assert self.ay is not None
            for _ in range(spf):
                s = int(self.ay.sample() * gain)
                pcm.extend(s.to_bytes(2, "little", signed=True))
        return bytes(pcm)


def run(
    rom: bytes,
    ids: list[int],
    *,
    sfx: bool = False,
    names: dict[int, str] | None = None,
    out_dir: str = ".",
    rate: int = 22050,
    loops: int = 8,
    min_seconds: float = 20.0,
    seconds: float | None = None,
    cpu_base: int = CPU_BASE,
) -> None:
    names = names or {}
    for i in ids:
        drv = Driver(rom, cpu_base)
        name = names.get(i, "%02X" % i)
        path = os.path.join(out_dir, name + ".wav")
        pcm = drv.render(
            i, rate, sfx=sfx, loops=loops,
            min_seconds=min_seconds, seconds=seconds,
        )
        write_wav(path, rate, pcm)
        sec = len(pcm) / (2 * rate)
        print("0x%02X  %s  %.2fs  %s" % (i, name, sec, path))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rom", help="linear ROM image (CPU 4000-BFFF)")
    ap.add_argument("--id", type=lambda s: int(s, 0), help="single play id")
    ap.add_argument("--sfx", action="store_true")
    ap.add_argument("--loops", type=int, default=8)
    ap.add_argument("--min-seconds", type=float, default=20.0)
    ap.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--rate", type=int, default=22050)
    ap.add_argument("-o", "--out", default=".")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=CPU_BASE)
    args = ap.parse_args(argv)
    if not os.path.isfile(args.rom):
        sys.exit("no ROM: %s" % args.rom)
    if args.id is None:
        sys.exit("pass --id")
    rom = open(args.rom, "rb").read()
    run(
        rom, [args.id], sfx=args.sfx, out_dir=args.out, rate=args.rate,
        loops=args.loops, min_seconds=args.min_seconds, seconds=args.seconds,
        cpu_base=args.base,
    )


if __name__ == "__main__":
    main()
