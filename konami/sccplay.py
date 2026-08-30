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

"""Render Konami 8-channel packed-PSG + SCC bytecode to WAV.

Reimplements the King's Valley II driver (sound_play 18-byte packed header,
8 slots, sound_tick). AY-3-8910 + Konami SCC. Recognizable, not analog-accurate.

Not Vampire Killer's 6-byte music-rec driver (that is psgplay.py).

Usage:
  tools/workbench/konami/sccplay.py Game.rom --map 4@6000,5@8000,6@A000 \\
      --ptr 0x6F2E --id 5 -o music/
"""
from __future__ import annotations

import argparse
import os
import struct
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from psgplay import (
    AY,
    AY_VOL,
    BankMap,
    FRAME_HZ,
    PSG_HZ,
    parse_id_range,
    parse_name,
    write_wav,
)

CH_STRIDE = 0x33
CH_BASE = [0xE000 + i * CH_STRIDE for i in range(8)]
CH_MASK = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80]
NOTE_CPU = 0x6480
ENV_CPU = (0x76A0, 0x77E1, 0x77FA, 0x7813, 0x782C, 0x7845)
WAVE_PTR_CPU = 0x7210
MIX_PSG = (
    (0x89, 0x81, 0x88, 0x80),
    (0x92, 0x82, 0x90, 0x80),
    (0xA4, 0x84, 0xA0, 0x80),
)
TEMPLATE = bytes([0x01]) + bytes(0x2D)  # +4 duration=1, then zeros (0x2E bytes)
SCC_HZ = PSG_HZ * 2  # 3.579545 MHz


class SCC:
    """Konami SCC: 5 channels, 32-byte signed waves; ch4 shares ch3's table."""

    def __init__(self, sample_rate: int):
        self.sr = sample_rate
        self.wave = [bytearray(32) for _ in range(4)]
        self.period = [1] * 5
        self.vol = [0] * 5
        self.enable = 0
        self.pos = [0] * 5
        self.phase = [0.0] * 5
        self.step = SCC_HZ / sample_rate

    def sample(self) -> int:
        acc = 0
        for ch in range(5):
            if not (self.enable & (1 << ch)):
                continue
            v = self.vol[ch] & 0x0F
            if v == 0:
                continue
            p = self.period[ch] or 1
            self.phase[ch] += self.step / p
            wch = 3 if ch == 4 else ch
            s = self.wave[wch][int(self.phase[ch]) & 31]
            if s >= 128:
                s -= 256
            acc += s * AY_VOL[v]
        acc //= 128 * 4
        if acc > 32767:
            return 32767
        if acc < -32768:
            return -32768
        return acc


class Driver:
    def __init__(self, rom: bytes, mapper: BankMap, ptr_tbl: int):
        self.rom = rom
        self.mapper = mapper
        self.ptr_tbl = ptr_tbl
        self.ram = bytearray(0x200)  # E000-E1FF
        self.ay = None  # type: AY | None
        self.scc = None  # type: SCC | None
        self.fda2 = 0
        self.jmp_hits = 0
        self._cmd_guard = 0

    def peek(self, cpu: int) -> int:
        return self.rom[self.mapper.cpu_off(cpu & 0xFFFF)]

    def peek16(self, cpu: int) -> int:
        return self.peek(cpu) | (self.peek((cpu + 1) & 0xFFFF) << 8)

    def rb(self, addr: int) -> int:
        return self.ram[addr - 0xE000]

    def wb(self, addr: int, v: int) -> None:
        self.ram[addr - 0xE000] = v & 0xFF

    def chb(self, base: int, off: int) -> int:
        return self.rb(base + off)

    def chw(self, base: int, off: int, v: int) -> None:
        self.wb(base + off, v)

    def chptr(self, base: int) -> int:
        return self.chb(base, 2) | (self.chb(base, 3) << 8)

    def setptr(self, base: int, cpu: int) -> None:
        self.chw(base, 2, cpu & 0xFF)
        self.chw(base, 3, cpu >> 8)

    def wrpsg(self, reg: int, val: int) -> None:
        assert self.ay is not None
        self.ay.write(reg, val)

    def play(
        self,
        sid: int,
        sample_rate: int,
        loops: int,
        max_seconds: float,
        min_seconds: float,
        sfx: bool,
    ):
        self.ay = AY(sample_rate)
        self.scc = SCC(sample_rate)
        self.ram[:] = bytes(0x200)
        self.fda2 = 0
        self.jmp_hits = 0
        self.wb(0xE1E3, 0xBF)
        self.wrpsg(7, 0xBF)
        self.play_id(sid)

        spf = int(round(sample_rate / FRAME_HZ))
        max_frames = int(max_seconds * FRAME_HZ)
        fade_frames = int(0.12 * FRAME_HZ) if sfx else int(FRAME_HZ)
        pcm = bytearray()
        stop_at = None  # type: int | None
        min_frames = int(min_seconds * FRAME_HZ)

        for frame in range(max_frames + fade_frames + 1):
            self.sound_tick()
            if stop_at is None:
                if self._all_idle():
                    stop_at = frame + fade_frames
                elif (
                    not sfx
                    and self.jmp_hits >= max(1, loops)
                    and frame > min_frames
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
            for _ in range(spf):
                s = self.ay.sample() + self.scc.sample()
                s = int(s * gain)
                if s > 32767:
                    s = 32767
                elif s < -32768:
                    s = -32768
                pcm.extend(struct.pack("<h", s))
        return bytes(pcm)

    def _all_idle(self) -> bool:
        return all(self.chb(b, 0) == 0 for b in CH_BASE)

    def play_id(self, sid: int) -> None:
        # sound_play without 0x80-0x84 special cases (catalogue uses 1-0x41).
        self.wb(0xE1CC, sid)
        hdr = self.peek16(self.ptr_tbl + (sid - 1) * 2)
        for i in range(18):
            self.wb(0xE1CD + i, self.peek((hdr + i) & 0xFFFF))
        flags = self.rb(0xE1CD)
        pri = self.rb(0xE1CE)
        ix = 0xE1CF
        for bit, base in zip(range(7, -1, -1), CH_BASE):
            if not (flags & (1 << bit)):
                continue
            self._init_slot(base)
            self._maybe_start(base, pri, sid, ix)
            ix += 2

    def _init_slot(self, base: int) -> None:
        for off in (0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x26):
            self.chw(base, off, 0)

    def _maybe_start(self, base: int, pri: int, sid: int, word_at: int) -> None:
        if pri < self.chb(base, 1):
            return
        ptr = self.rb(word_at) | (self.rb(word_at + 1) << 8)
        self.chw(base, 0, sid)
        self.chw(base, 1, pri)
        self.chw(base, 2, ptr & 0xFF)
        self.chw(base, 3, ptr >> 8)
        for i, b in enumerate(TEMPLATE):
            self.chw(base, 4 + i, b)

    def sound_tick(self) -> None:
        self.wrpsg(7, self.rb(0xE1E3))
        e1fd = 0xE1FD
        if self.fda2 != self.rb(e1fd):
            for base in (0xE099, 0xE0CC, 0xE0FF, 0xE132):
                self.chw(base, 0x0F, self.chb(base, 0x0F) | 0x80)
            self.wb(e1fd, self.fda2)
        self.wb(e1fd, (self.rb(e1fd) + 1) & 0xFF)
        self.fda2 = self.rb(e1fd)

        g = self.rb(0xE1CB)
        if g & 2:
            self.wb(0xE1E4, 0x08)
            self._tick_ch(0xE099)
            self.wb(0xE1E3, 0xBF)
            self._cmd_e8_mute_noise()
            self._apply_hw()
            return
        if g & 1:
            self._fade_bit0()
        if g & 0x10:
            self._fade_bit4()
        for mask, base in zip(CH_MASK, CH_BASE):
            self.wb(0xE1E4, mask)
            self._tick_ch(base)
        self._apply_hw()

    def _cmd_e8_mute_noise(self) -> None:
        v = self.rb(0xE1E7) & 0x1F
        self.wb(0xE1E7, v)

    def _fade_bit0(self) -> None:
        # sub_67b1h — countdown then stop channels. Catalogue play is a solo
        # id, so this only matters if the stream sets E1CB itself.
        pass

    def _fade_bit4(self) -> None:
        pass

    def _tick_ch(self, base: int) -> None:
        if self.chb(base, 0) == 0:
            return
        d = (self.chb(base, 4) - 1) & 0xFF
        self.chw(base, 4, d)
        if d != 0:
            self._sustain(base)
            return
        if self.chb(base, 0x0D) & 0x40:
            self.chw(base, 0x0D, self.chb(base, 0x0D) | 0x20)
        self._fetch(base, self.chptr(base))

    def _fetch(self, base: int, hl: int) -> int:
        self._cmd_guard = 0
        while True:
            self._cmd_guard += 1
            if self._cmd_guard > 4096:
                raise RuntimeError("command loop at 0x%04X" % hl)
            a = self.peek(hl)
            if a == 0xFF:
                self._stop_ch(base)
                return hl
            if a >= 0xD0:
                hl = self._command(base, hl, a)
                hl = (hl + 1) & 0xFFFF
                continue
            mode = self.chb(base, 9)
            if mode & 1:
                return self._note(base, hl)
            if mode & 2:
                return self._raw(base, hl)
            if mode & 0x1C:
                return self._env_note(base, hl)
            return hl

    def _advance(self, base: int, hl: int) -> int:
        hl = (hl + 1) & 0xFFFF
        self.setptr(base, hl)
        return hl

    def _note(self, base: int, hl: int) -> int:
        nibble = self.peek(hl) & 0x0F
        scale = self.chb(base, 0x14)
        self.chw(base, 4, (scale * (nibble + 1)) & 0xFF)
        note = self.peek(hl) >> 4
        self._advance(base, hl)
        if self.chb(base, 9) & 0x80:
            return hl
        if note >= 0x0C:
            self.chw(base, 0x0D, self.chb(base, 0x0D) & 0xF0)
            return hl
        period = self.peek(NOTE_CPU + note)
        octv = self.chb(base, 0x16)
        if octv:
            if self.chb(base, 0x0D) & 0x80:
                octv = (octv - self.chb(base, 0x2F)) & 0xFF
                if octv == 0 or octv & 0x80:
                    octv = 0
            for _ in range(octv):
                period = (period << 1) & 0xFFFF
        self.chw(base, 0x10, period & 0xFF)
        self.chw(base, 0x11, period >> 8)
        vol = self.chb(base, 0x15)
        g = self.rb(0xE1CB)
        if g & 0x11:
            vol = self._vol_fade(base, vol)
        self.chw(base, 0x12, vol)
        self.chw(base, 0x0D, (self.chb(base, 0x0D) & 0xF0) | 0x02)
        self._key_on(base)
        return hl

    def _vol_fade(self, base: int, vol: int) -> int:
        # sub_6811h
        a = self.chb(0xE033, 0)
        c = self.chb(0xE066, 0)
        if a != c:
            if (self.rb(0xE1E4) & 0xF3) == 0:
                return vol
        if self.chb(base, 0x0D) & 4:
            return 0
        sub = self.rb(0xE1E2)
        out = vol - sub
        return 0 if out < 0 else out & 0xFF

    def _raw(self, base: int, hl: int) -> int:
        flags = self.chb(base, 0x0D) & 3
        if flags != 0:
            b = self.peek(hl)
            e = self.chb(base, 0x0E)
            if e & 0x40:
                self.chw(base, 0x10, b)
            elif e & 0x20:
                self.chw(base, 0x11, b >> 4)
                self._raw_vol(base, b & 0x0F)
            elif flags == 1:
                self._raw_vol(base, b & 0x0F)
            else:
                hl = (hl + 1) & 0xFFFF
                self.chw(base, 0x10, self.peek(hl))
                self.chw(base, 0x11, b & 0x0F)
                self._raw_vol(base, b >> 4)
            vol = self.chb(base, 0x12)
            g = self.rb(0xE1CB)
            if g & 0x11:
                vol = self._vol_fade(base, vol)
            self.chw(base, 0x12, vol)
            self._key_on(base)
        if self.chb(base, 9) & 0x80:
            return hl
        self._advance(base, hl)
        self.chw(base, 4, self.chb(base, 0x13))
        return hl

    def _raw_vol(self, base: int, b: int) -> None:
        mask = self.rb(0xE1E4)
        if mask < 8 and (self.chb(base, 0x0D) & 4):
            b = 0x10
        b = (b + 2) & 0xFF
        self.chw(base, 0x12, b)
        vol = b
        g = self.rb(0xE1CB)
        if g & 0x11:
            vol = self._vol_fade(base, vol)
        self.chw(base, 0x12, vol)

    def _env_note(self, base: int, hl: int) -> int:
        self.chw(base, 9, self.chb(base, 9) | 0x80)
        self._note(base, hl)
        note = self.peek(hl) >> 4
        table = self._env_table(base)
        stream = self.peek16(table + (note & 0x0F) * 2)
        self.chw(base, 9, self.chb(base, 9) | 2)
        env_hl = self._fetch(base, stream)
        self.chw(base, 9, self.chb(base, 9) & ~0x82)
        self.chw(base, 0x19, self.chb(base, 0x13))
        env_hl = (env_hl + 1) & 0xFFFF
        self.chw(base, 0x17, env_hl & 0xFF)
        self.chw(base, 0x18, env_hl >> 8)
        self.chw(base, 0x0E, self.chb(base, 0x0E) | 1)
        return hl

    def _env_table(self, base: int) -> int:
        sel = self.chb(base, 0x2C)
        mode = self.chb(base, 9)
        if mode & 4:
            return ENV_CPU[1 if sel == 1 else 0]
        if mode & 8:
            return ENV_CPU[3 if sel == 1 else 2]
        if mode & 0x10:
            return ENV_CPU[5 if sel == 1 else 4]
        return ENV_CPU[0]

    def _key_on(self, base: int) -> None:
        self._copy_period(base)
        self.chw(base, 0x0E, self.chb(base, 0x0E) & ~0x10)
        self.chw(base, 0x0F, self.chb(base, 0x0F) & 0xD7)
        for off in (0x1D, 0x1E, 0x1F, 0x20):
            self.chw(base, off, 0)
        self.chw(base, 0x0F, self.chb(base, 0x0F) | 4)
        vol = self.chb(base, 0x12)
        if self.chb(base, 0x0E) & 0x80:
            vol = vol - self.chb(base, 0x29)
            if vol < 0:
                vol = 0
        self.chw(base, 0x0C, vol)
        if self.rb(0xE1E4) < 8 and (self.chb(base, 0x0D) & 4):
            return
        if not (self.chb(base, 0x0F) & 2):
            return
        self.chw(base, 0x0C, self.chb(base, 0x25))
        self.chw(base, 0x0F, self.chb(base, 0x0F) & ~4)

    def _copy_period(self, base: int) -> None:
        e = self.chb(base, 0x10)
        d = self.chb(base, 0x11)
        if self.chb(base, 0x0E) & 2:
            e = (e + self.chb(base, 0x26)) & 0xFF
            if e < self.chb(base, 0x26):
                d = (d + 1) & 0xFF
        self.chw(base, 0x0A, e)
        self.chw(base, 0x0B, d)

    def _sustain(self, base: int) -> None:
        if self.chb(base, 0x0E) & 1:
            n = (self.chb(base, 0x19) - 1) & 0xFF
            self.chw(base, 0x19, n)
            if n != 0:
                return
            hl = self.chb(base, 0x17) | (self.chb(base, 0x18) << 8)
            if self.peek(hl) == 0xFF:
                self.chw(base, 0x0E, self.chb(base, 0x0E) & ~1)
                self.chw(base, 0x0C, 0)
                self.chw(base, 0x0D, self.chb(base, 0x0D) & 0xF0)
                return
            self.chw(base, 9, self.chb(base, 9) | 0x80)
            self.chw(base, 9, self.chb(base, 9) | 2)
            env_hl = self._fetch(base, hl)
            self.chw(base, 9, self.chb(base, 9) & ~0x82)
            self.chw(base, 0x19, self.chb(base, 0x13))
            env_hl = (env_hl + 1) & 0xFFFF
            self.chw(base, 0x17, env_hl & 0xFF)
            self.chw(base, 0x18, env_hl >> 8)
            self.chw(base, 0x0E, self.chb(base, 0x0E) | 1)
            return
        if self.chb(base, 0x0D) & 0x40:
            self._slide(base)
        if self.chb(base, 0x0E) & 4:
            self._vibrato(base)
        if self.chb(base, 0x0F) & 1:
            self._adsr(base)

    def _slide(self, base: int) -> None:
        if not (self.chb(base, 0x0D) & 0x20):
            return
        if self.chb(base, 0x31) & 8:
            self.chw(base, 0x30, (self.chb(base, 0x30) - 1) & 0xFF)
            if not (self.chb(base, 0x30) & 8):
                self._slide_reset(base)
                return
            b = (self.chb(base, 0x30) - 8) & 0xFF
            step = self.chb(base, 0x32)
            de = (step * b) & 0xFFFF
            p = self.chb(base, 0x10) | (self.chb(base, 0x11) << 8)
            p = (p - de) & 0xFFFF
            self.chw(base, 0x0A, p & 0xFF)
            self.chw(base, 0x0B, p >> 8)
            return
        if self.chb(base, 0x30) == 0:
            self._slide_reset(base)
            return
        self.chw(base, 0x30, (self.chb(base, 0x30) - 1) & 0xFF)
        if self.chb(base, 0x30) == 0:
            self._slide_reset(base)
            return
        step = self.chb(base, 0x32)
        n = self.chb(base, 0x30)
        add = (step * n) & 0xFFFF
        p = (self.chb(base, 0x10) | (self.chb(base, 0x11) << 8)) + add
        self.chw(base, 0x0A, p & 0xFF)
        self.chw(base, 0x0B, (p >> 8) & 0xFF)

    def _slide_reset(self, base: int) -> None:
        self.chw(base, 0x0D, self.chb(base, 0x0D) & ~0x20)
        self.chw(base, 0x0A, self.chb(base, 0x10))
        self.chw(base, 0x0B, self.chb(base, 0x11))
        self.chw(base, 0x30, self.chb(base, 0x31))

    def _vibrato(self, base: int) -> None:
        self.chw(base, 0x1E, (self.chb(base, 0x1E) + 1) & 0xFF)
        t = self.chb(base, 0x1E)
        e = self.chb(base, 0x0E)
        if (e & 0x10) == 0 and (e & 8):
            if t != self.chb(base, 0x1A):
                return
            self.chw(base, 0x1E, 0)
            self.chw(base, 0x0E, e | 0x10)
        else:
            if t != self.chb(base, 0x1B):
                return
        lo = self.chb(base, 0x0A)
        hi = self.chb(base, 0x0B)
        depth = self.chb(base, 0x1C)
        self.chw(base, 0x1D, self.chb(base, 0x1D) ^ 0xFF)
        if self.chb(base, 0x1D):
            lo = (lo - depth) & 0xFF
            if lo > (lo + depth) & 0xFF:
                hi = (hi - 1) & 0xFF
        else:
            lo = (lo + depth) & 0xFF
            if lo < depth:
                hi = (hi + 1) & 0xFF
        self.chw(base, 0x0A, lo)
        self.chw(base, 0x0B, hi)
        self.chw(base, 0x1E, 0)

    def _adsr(self, base: int) -> None:
        if self.rb(0xE1E4) < 8 and (self.chb(base, 0x0D) & 4):
            return
        e = self.chb(base, 0x0C)
        self.chw(base, 0x1F, (self.chb(base, 0x1F) + 1) & 0xFF)
        b = self.chb(base, 0x1F)
        if self.chb(base, 0x24) >= self.chb(base, 4):
            self.chw(base, 0x0F, self.chb(base, 0x0F) | 0x20)
        f = self.chb(base, 0x0F)
        if f & 0x20:
            if self.chb(base, 4) < self.chb(base, 0x24):
                e = max(0, e - 1)
            self.chw(base, 0x0C, e)
            return
        if f & 8:
            if f & 0x10:
                if b != self.chb(base, 0x23):
                    self.chw(base, 0x0C, e)
                    return
                sub = self.chb(base, 0x22)
                e = 0 if e < sub else e - sub
                self.chw(base, 0x0F, f | 0x20)
                self.chw(base, 0x0C, e)
                return
            if b != self.chb(base, 0x22):
                self.chw(base, 0x0C, e)
                return
            e = max(0, e - 1)
            self.chw(base, 0x20, (self.chb(base, 0x20) + 1) & 0xFF)
            self.chw(base, 0x1F, 0)
            if self.chb(base, 0x20) != self.chb(base, 0x23):
                self.chw(base, 0x0C, e)
                return
            self.chw(base, 0x0F, f | 0x20)
            self.chw(base, 0x0C, e)
            return
        if f & 4:
            e = max(0, e - 1)
            if b < self.chb(base, 0x21):
                self.chw(base, 0x0C, e)
                return
            self.chw(base, 0x1F, 0)
            self.chw(base, 0x0F, f | 8)
            self.chw(base, 0x0C, e)
            return
        e = (e + 1) & 0xFF
        if e < self.chb(base, 0x12):
            self.chw(base, 0x0C, e)
            return
        self.chw(base, 0x0F, f | 4)
        self.chw(base, 0x0C, self.chb(base, 0x12))
        self.chw(base, 0x1F, 0)

    def _stop_ch(self, base: int) -> None:
        for off in (0, 1, 5, 6, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F):
            self.chw(base, off, 0)
        mask = self.rb(0xE1E4)
        if mask >= 8:
            return
        e7 = self.rb(0xE1E7)
        if mask == 4:
            e7 &= ~3
            if (e7 & 8) and (e7 & 4):
                e7 = (e7 | 4) & ~8
            self.wb(0xE1E7, e7)
            return
        self.wb(0xE1E7, e7 & ~0x0C)

    def _command(self, base: int, hl: int, op: int) -> int:
        if op < 0xE0:
            return self._cmd_dx(base, hl, op)
        n = op & 0x1F
        if n in (0, 2):
            return self._cmd_e0(base, hl)
        if n in (1, 3):
            return self._cmd_e1(base, hl)
        if n == 4:
            return self._cmd_e4(base, hl)
        if n == 5:
            return self._cmd_e5(base, hl)
        if n == 6:
            return self._cmd_e6(base, hl)
        if n == 7:
            return self._cmd_e7(base, hl)
        if n == 8:
            return self._cmd_e8(base, hl)
        if n == 9:
            hl = (hl + 1) & 0xFFFF
            self.chw(base, 0x14, self.peek(hl))
            return hl
        if n == 0xA:
            hl = (hl + 1) & 0xFFFF
            self.chw(base, 0x15, self.peek(hl))
            return hl
        if n == 0xB:
            return self._cmd_eb(base, hl)
        if n == 0xC:
            self.chw(base, 0x0F, self.chb(base, 0x0F) & ~1)
            self.chw(base, 0x0F, self.chb(base, 0x0F) & ~2)
            return hl
        if n == 0xD:
            hl = (hl + 1) & 0xFFFF
            self.chw(base, 0x25, self.peek(hl))
            return hl
        if n == 0xE:
            hl = (hl + 1) & 0xFFFF
            self.chw(base, 0x26, self.peek(hl))
            self.chw(base, 0x0E, self.chb(base, 0x0E) | 2)
            return hl
        if n == 0xF:
            self.chw(base, 0x0E, self.chb(base, 0x0E) & ~2)
            return hl
        if n == 0x10:
            self.chw(base, 0x0E, self.chb(base, 0x0E) & 0xE2)
            return hl
        if n == 0x11:
            hl = (hl + 1) & 0xFFFF
            self.chw(base, 0x0E, self.chb(base, 0x0E) | 0x14)
            b = self.peek(hl)
            self.chw(base, 0x1C, b & 0x0F)
            self.chw(base, 0x1B, b >> 4)
            return hl
        if n == 0x12:
            hl = (hl + 1) & 0xFFFF
            self.chw(base, 0x1A, self.peek(hl))
            self.chw(base, 0x0E, self.chb(base, 0x0E) | 0x0C)
            return hl
        if n == 0x13:
            self.chw(base, 0x0E, self.chb(base, 0x0E) & ~8)
            return hl
        if n == 0x14:
            self.chw(base, 0x0E, self.chb(base, 0x0E) | 0x40)
            return hl
        if n == 0x15:
            self.chw(base, 0x0E, self.chb(base, 0x0E) | 0x20)
            return hl
        if n == 0x16:
            self.chw(base, 0x0E, self.chb(base, 0x0E) & 0x9F)
            return hl
        if n == 0x17:
            self.chw(base, 0x0E, self.chb(base, 0x0E) | 0x80)
            hl = (hl + 1) & 0xFFFF
            self.chw(base, 0x29, self.peek(hl))
            return hl
        if n == 0x18:
            hl = (hl + 1) & 0xFFFF
            idx = self.peek(hl)
            addr = WAVE_PTR_CPU + idx * 2
            w = self.peek16(addr)
            self.chw(base, 0x27, w & 0xFF)
            self.chw(base, 0x28, w >> 8)
            self.chw(base, 0x0F, self.chb(base, 0x0F) | 0x80)
            return hl
        if n == 0x19:
            dest, land, ret_addr = self._read_abs(hl)
            self.chw(base, 7, ret_addr & 0xFF)
            self.chw(base, 8, ret_addr >> 8)
            return land
        if n == 0x1A:
            return self.chb(base, 7) | (self.chb(base, 8) << 8)
        if n == 0x1B:
            return self._loop_abs(base, hl, 5)
        if n == 0x1C:
            return self._loop_abs(base, hl, 6)
        if n == 0x1D:
            _dest, land, _ret = self._read_abs(hl)
            self.jmp_hits += 1
            return land
        if n == 0x1E:
            return self._cmd_fe(base, hl)
        return hl

    def _read_abs(self, hl: int):
        # sub_6a9ch: word at hl+1; HL=dest-1 (post-inc lands on dest);
        # DE=address of the high byte (call/ret save).
        lo_at = (hl + 1) & 0xFFFF
        hi_at = (hl + 2) & 0xFFFF
        dest = self.peek(lo_at) | (self.peek(hi_at) << 8)
        return dest, (dest - 1) & 0xFFFF, hi_at

    def _loop_abs(self, base: int, hl: int, ctr: int) -> int:
        hl = (hl + 1) & 0xFFFF
        n = (self.chb(base, ctr) + 1) & 0xFF
        if n == self.peek(hl):
            self.chw(base, ctr, 0)
            return (hl + 2) & 0xFFFF
        self.chw(base, ctr, n)
        dest = self.peek16((hl + 1) & 0xFFFF)
        return (dest - 1) & 0xFFFF

    def _cmd_dx(self, base: int, hl: int, op: int) -> int:
        lo = op & 0x0F
        if lo < 6:
            self.chw(base, 0x16, lo)
            self.chw(base, 0x2C, lo)
            return hl
        if lo == 7:
            self.chw(base, 0x0D, self.chb(base, 0x0D) & ~0x60)
            return hl
        if lo == 8:
            self.chw(base, 0x0D, self.chb(base, 0x0D) | 0x60)
            hl = (hl + 1) & 0xFFFF
            b = self.peek(hl)
            self.chw(base, 0x30, b >> 4)
            self.chw(base, 0x31, b >> 4)
            self.chw(base, 0x32, b & 0x0F)
            return hl
        if lo == 9:
            _dest, land, ret_addr = self._read_abs(hl)
            self.chw(base, 0x2D, ret_addr & 0xFF)
            self.chw(base, 0x2E, ret_addr >> 8)
            return land
        if lo == 0xA:
            return self.chb(base, 0x2D) | (self.chb(base, 0x2E) << 8)
        if lo == 0xB:
            hl = (hl + 1) & 0xFFFF
            n = (self.chb(base, 5) + 1) & 0xFF
            if n == self.peek(hl):
                self.chw(base, 5, 0)
                return (hl + 1) & 0xFFFF
            self.chw(base, 5, n)
            hl = (hl + 1) & 0xFFFF
            back = self.peek(hl)
            l = (hl - back) & 0xFFFF
            return (l - 1) & 0xFFFF
        if lo == 0xC:
            self.chw(base, 0x0D, self.chb(base, 0x0D) | 0x80)
            hl = (hl + 1) & 0xFFFF
            self.chw(base, 0x2F, self.peek(hl))
            return hl
        if lo == 0xD:
            self.chw(base, 0x0D, self.chb(base, 0x0D) & ~0x80)
            return hl
        if lo == 0xE:
            hl = (hl + 1) & 0xFFFF
            self.chw(base, 1, self.peek(hl))
            return hl
        self.chw(base, 0x0E, self.chb(base, 0x0E) & ~0x80)
        return hl

    def _cmd_e0(self, base: int, hl: int) -> int:
        self.chw(base, 0x0E, self.chb(base, 0x0E) & ~0x40)
        mode = self.peek(hl) & 3
        self.chw(base, 0x0D, mode)
        hl = (hl + 1) & 0xFFFF
        self.chw(base, 0x13, self.peek(hl))
        if mode == 0:
            return (hl - 1) & 0xFFFF
        return hl

    def _cmd_e1(self, base: int, hl: int) -> int:
        e7 = self.rb(0xE1E7)
        if self.rb(0xE1E4) == 4:
            e7 = (e7 | 1) & ~2
        else:
            e7 = (e7 | 4) & ~8
        self.wb(0xE1E7, e7)
        return self._cmd_e0(base, hl)

    def _cmd_e4(self, base: int, hl: int) -> int:
        hl = (hl + 1) & 0xFFFF
        noise = self.peek(hl) & 0x1F
        e7 = self.rb(0xE1E7)
        if self.rb(0xE1E4) == 4:
            self.wb(0xE1E5, noise)
            self.wb(0xE1E7, (e7 | 1) & ~2)
        else:
            self.wb(0xE1E6, noise)
            self.wb(0xE1E7, (e7 | 4) & ~8)
        return hl

    def _cmd_e5(self, base: int, hl: int) -> int:
        hl = (hl + 1) & 0xFFFF
        self.chw(base, 0x0D, self.chb(base, 0x0D) & ~8)
        self.wb(0xE1E8, self.peek(hl))
        self.wb(0xE1E7, self.rb(0xE1E7) | 0x20)
        return self._cmd_e6_from(base, hl)

    def _cmd_e6(self, base: int, hl: int) -> int:
        return self._cmd_e6_from(base, hl)

    def _cmd_e6_from(self, base: int, hl: int) -> int:
        hl = (hl + 1) & 0xFFFF
        self.wb(0xE1EA, self.peek(hl))
        self.wb(0xE1E7, self.rb(0xE1E7) | 0x40)
        return self._cmd_e7_from(base, hl)

    def _cmd_e7(self, base: int, hl: int) -> int:
        return self._cmd_e7_from(base, hl)

    def _cmd_e7_from(self, base: int, hl: int) -> int:
        hl = (hl + 1) & 0xFFFF
        self.wb(0xE1E9, self.peek(hl))
        self.wb(0xE1E7, self.rb(0xE1E7) | 0x80)
        self.chw(base, 0x0D, self.chb(base, 0x0D) | 4)
        return hl

    def _cmd_e8(self, base: int, hl: int) -> int:
        self.wb(0xE1E7, self.rb(0xE1E7) & 0x1F)
        self.chw(base, 0x0D, self.chb(base, 0x0D) & 0xF3)
        return hl

    def _cmd_eb(self, base: int, hl: int) -> int:
        self.chw(base, 0x0F, self.chb(base, 0x0F) & 0x80)
        hl = (hl + 1) & 0xFFFF
        b = self.peek(hl)
        hi = b >> 4
        if hi < 8:
            self.chw(base, 0x0F, self.chb(base, 0x0F) | 4)
        hi = (hi & ~8) + 1
        if not (self.chb(base, 0x0F) & 4):
            self.chw(base, 0x0F, self.chb(base, 0x0F) | 2)
        self.chw(base, 0x21, hi)
        lo = b & 0x0F
        if lo >= 8:
            self.chw(base, 0x0F, self.chb(base, 0x0F) | 0x10)
        lo = (lo & ~8) + 1
        self.chw(base, 0x22, lo)
        hl = (hl + 1) & 0xFFFF
        b = self.peek(hl)
        self.chw(base, 0x23, b >> 4)
        self.chw(base, 0x24, b & 0x0F)
        self.chw(base, 0x0F, self.chb(base, 0x0F) | 1)
        return hl

    def _cmd_fe(self, base: int, hl: int) -> int:
        hl = (hl + 1) & 0xFFFF
        old = self.chb(base, 9)
        new = self.peek(hl)
        self.chw(base, 9, new)
        if new == 1:
            if old != 1:
                self.chw(base, 0x0E, self.chb(base, 0x2A))
                self.chw(base, 0x0F, self.chb(base, 0x2B))
            return hl
        if old != 1:
            return hl
        self.chw(base, 0x2A, self.chb(base, 0x0E))
        self.chw(base, 0x2B, self.chb(base, 0x0F))
        self.chw(base, 0x0E, 0)
        self.chw(base, 0x0F, 0)
        return hl

    def _apply_hw(self) -> None:
        assert self.ay is not None and self.scc is not None
        # Collision hack sub_6bafh: if both A and C have bit0 of +0d, force A to 2.
        if (self.chb(0xE000, 0x0D) & 1) and (self.chb(0xE066, 0x0D) & 1):
            self.chw(0xE000, 0x0D, 2)
        for i, base in enumerate((0xE000, 0xE033, 0xE066)):
            lo = self.chb(base, 0x0A)
            hi = self.chb(base, 0x0B)
            vol = self.chb(base, 0x0C)
            flags = self.chb(base, 0x0D)
            self.wrpsg(i * 2, lo)
            self.wrpsg(i * 2 + 1, hi & 0x0F)
            if not (flags & 8):
                self.wrpsg(8 + i, vol & 0x1F)
                if flags & 4:
                    self.chw(base, 0x0D, flags | 8)
        e7 = self.rb(0xE1E7)
        if e7 & 1:
            self.wb(0xE1E7, (e7 & ~1) | 2)
            self.wrpsg(6, self.rb(0xE1E5))
        elif not (e7 & 2) and (e7 & 4):
            self.wb(0xE1E7, (e7 & ~4) | 8)
            self.wrpsg(6, self.rb(0xE1E6))
        e7 = self.rb(0xE1E7)
        if e7 & 0x80:
            self.wb(0xE1E7, e7 & ~0x80)
            self.wrpsg(11, self.rb(0xE1E9))
            e7 = self.rb(0xE1E7)
            if e7 & 0x40:
                self.wb(0xE1E7, e7 & ~0x40)
                self.wrpsg(12, self.rb(0xE1EA))
                e7 = self.rb(0xE1E7)
                if e7 & 0x20:
                    self.wb(0xE1E7, e7 & ~0x20)
                    self.wrpsg(13, self.rb(0xE1E8))
        mix = 0
        for i, base in enumerate((0xE000, 0xE033, 0xE066)):
            mix |= MIX_PSG[i][self.chb(base, 0x0D) & 3]
        self.wb(0xE1E3, mix)
        self.wrpsg(7, mix)

        enable = 0
        for i, base in enumerate((0xE099, 0xE0CC, 0xE0FF, 0xE132, 0xE165)):
            p = self.chb(base, 0x0A) | ((self.chb(base, 0x0B) & 0x0F) << 8)
            self.scc.period[i] = p or 1
            self.scc.vol[i] = self.chb(base, 0x0C) & 0x0F
            if self.chb(base, 0x0D):
                enable |= 1 << i
            if i < 4 and (self.chb(base, 0x0F) & 0x80):
                self.chw(base, 0x0F, self.chb(base, 0x0F) & ~0x80)
                w = self.chb(base, 0x27) | (self.chb(base, 0x28) << 8)
                for k in range(32):
                    self.scc.wave[i][k] = self.peek((w + k) & 0xFFFF)
        self.scc.enable = enable
        self.wb(0xE1FC, enable)


def header_pri(rom: bytes, mapper: BankMap, ptr_tbl: int, sid: int) -> int:
    hdr = rom[mapper.cpu_off(ptr_tbl + (sid - 1) * 2)] | (
        rom[mapper.cpu_off(ptr_tbl + (sid - 1) * 2 + 1)] << 8
    )
    return rom[mapper.cpu_off((hdr + 1) & 0xFFFF)]


def run(
    rom: bytes,
    mapper: BankMap,
    ptr_tbl: int,
    ids: list[int],
    *,
    sfx: bool = False,
    names: dict[int, str] | None = None,
    out_dir: str = ".",
    rate: int = 22050,
    loops: int = 2,
    min_seconds: float = 20.0,
    seconds: float | None = None,
) -> None:
    names = names or {}
    cap = (4.0 if sfx else 90.0) if seconds is None else seconds
    mins = 0.0 if sfx else min_seconds
    for i in ids:
        drv = Driver(rom, mapper, ptr_tbl)
        name = names.get(i, "%02X" % i)
        path = os.path.join(out_dir, name + ".wav")
        pcm = drv.play(i, rate, max(1, loops), cap, mins, sfx)
        write_wav(path, rate, pcm)
        sec = len(pcm) / (2 * rate)
        print("0x%02X  %s  %.2fs  %s" % (i, name, sec, path))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rom", help="ROM image")
    ap.add_argument(
        "--map",
        required=True,
        help="BANK@CPU windows (8 KiB), e.g. 4@6000,5@8000,6@A000",
    )
    ap.add_argument(
        "--ptr",
        type=lambda s: int(s, 0),
        required=True,
        help="word table; sound_play indexes id 1 as the first entry",
    )
    ap.add_argument("--sfx", action="store_true")
    ap.add_argument("--id", type=lambda s: int(s, 0))
    ap.add_argument("--ids", type=parse_id_range)
    ap.add_argument("--name", action="append", default=[], metavar="ID=STEM",
                    type=parse_name)
    ap.add_argument("--loops", type=int, default=2)
    ap.add_argument("--min-seconds", type=float, default=20.0)
    ap.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--rate", type=int, default=22050)
    ap.add_argument("-o", "--out", default=".")
    args = ap.parse_args(argv)
    if not os.path.isfile(args.rom):
        sys.exit("no ROM: %s" % args.rom)
    try:
        mapper = BankMap.parse(args.map)
    except ValueError as e:
        sys.exit(str(e))
    if args.id is not None:
        ids = [args.id]
    elif args.ids:
        ids = args.ids
    else:
        sys.exit("pass --id or --ids")
    rom = open(args.rom, "rb").read()
    run(
        rom, mapper, args.ptr, ids,
        sfx=args.sfx, names=dict(args.name), out_dir=args.out,
        rate=args.rate, loops=args.loops, min_seconds=args.min_seconds,
        seconds=args.seconds,
    )


if __name__ == "__main__":
    main()
