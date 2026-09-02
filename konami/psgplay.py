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

"""Render Konami packed-PSG bytecode through an AY-3-8910 model.

Reimplements the in-house 6-byte music-rec driver (3 PSG channels, 20-byte
channel template) so any title that shares that bytecode can be rendered by
pointing --map and the table addresses at its own banks.

AY generators match CocoaMSX ``AY8910.c`` (blueMSX): 16× oversample, log
volume, DC high-pass + 1-pole low-pass. Still not analog-accurate
(loop/fade heuristics on BGM).

Usage:
  tools/workbench/konami/psgplay.py Game.rom --map 2@8000,3@a000 \\
      --music-ptr 0xNNNN --sfx-ptr 0xNNNN \\
      --env-ptr 0xNNNN --env-alt 0xNNNN --note-tbl 0xNNNN \\
      --music-ids 0x80-0x8F --name 0x80=80_theme
  tools/workbench/konami/psgplay.py Game.rom --map ... --sfx --sfx-ids 1-0x10
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import wave

BANK_SIZE = 0x2000

# One octave, little-endian periods (note table). Also loaded from ROM.
NOTE_PERIODS = [
    0x1AB8, 0x1938, 0x17D0, 0x1678, 0x1534, 0x1404,
    0x12E4, 0x11D4, 0x10D4, 0x0FE4, 0x0F00, 0x0E28,
]

# The driver copies this 20-byte block to each music channel.
TEMPLATE = bytes([
    0x00, 0x00,  # +0 stream ptr (filled in)
    0x01, 0x00, 0x00,  # +2 flags (bit0=tone), +3 scale, +4 base vol
    0x00, 0x00, 0x00, 0x00,  # +5 decay start, +6 decay end, +7 octave, +8
    0x01, 0x00, 0x00,  # +9 duration=1 so the first tick fetches
    0x00, 0x00,  # +12 env ptr
    0x01, 0x01, 0x00,  # +14/+15 sfx reload, +16 loop count
    0x00, 0x00, 0x00,  # +17..+19 call return
])

# Mixer AND/OR pairs, indexed by channel 0..2.
MIX_TONE = [(0xFE, 0x08), (0xFD, 0x10), (0xFB, 0x20)]
MIX_NOISE = [(0xF7, 0x01), (0xEF, 0x02), (0xDF, 0x04)]
MIX_BOTH = [(0xF6, 0x00), (0xED, 0x00), (0xDB, 0x00)]
MIX_MUTE = [(0xFF, 0x09), (0xFF, 0x12), (0xFF, 0x24)]

# CocoaMSX AY8910.c (blueMSX): 1.5 dB steps from 0x26a9, then subtract [0].
_AY_VOLT_MUL = 0.70794578438413791080221494218943
_AY_REG_MASK = (
    0xFF, 0x0F, 0xFF, 0x0F, 0xFF, 0x0F, 0x1F, 0x3F,
    0x1F, 0x1F, 0x1F, 0xFF, 0xFF, 0x0F, 0xFF, 0xFF,
)


def _ay_volt_tables() -> tuple[list[int], list[int]]:
    v = 0x26A9
    tone = [0] * 16
    env = [0] * 32
    for i in range(15, -1, -1):
        iv = int(v)
        tone[i] = iv
        env[2 * i] = iv
        env[2 * i + 1] = iv
        v *= _AY_VOLT_MUL
    z = tone[0]
    return [x - z for x in tone], [x - env[0] for x in env]


AY_VOL, _AY_ENV_VOL = _ay_volt_tables()

PSG_HZ = 1_789_772.5  # MSX: 3.579545 MHz / 2
FRAME_HZ = 60.0


def _tdiv(n: int, d: int) -> int:
    """C99 toward-zero integer division."""
    return -(-n // d) if n < 0 else n // d


class BankMap:
    """CPU window -> 8 KiB ROM bank.  windows: [(cpu_base, bank), ...]."""

    def __init__(self, windows, bank_size=BANK_SIZE):
        self.bank_size = bank_size
        self.windows = []
        for cpu_base, bank in sorted(windows):
            self.windows.append((cpu_base, cpu_base + bank_size, bank))

    def cpu_off(self, cpu):
        cpu &= 0xFFFF
        for lo, hi, bank in self.windows:
            if lo <= cpu < hi:
                return bank * self.bank_size + (cpu - lo)
        raise ValueError("music pointer 0x%04X is outside the mapped banks" % cpu)

    @classmethod
    def parse(cls, spec):
        """Parse '2@8000,3@a000' -> BankMap."""
        windows = []
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "@" not in part:
                raise ValueError("map entry %r: want BANK@CPU (e.g. 2@8000)" % part)
            bank_s, base_s = part.split("@", 1)
            base_s = base_s.strip()
            cpu_base = int(base_s, 16)  # 8000, a000, or 0x8000
            windows.append((cpu_base, int(bank_s, 0)))
        if not windows:
            raise ValueError("empty --map")
        return cls(windows)


class Tables:
    __slots__ = ("music_ptr", "sfx_ptr", "env_ptr", "env_ptr_alt", "note_tbl")

    def __init__(self, music_ptr, sfx_ptr, env_ptr, env_ptr_alt, note_tbl):
        self.music_ptr = music_ptr
        self.sfx_ptr = sfx_ptr
        self.env_ptr = env_ptr
        self.env_ptr_alt = env_ptr_alt
        self.note_tbl = note_tbl


class AY:
    """AY-3-8910 generators from CocoaMSX ``AY8910.c`` (blueMSX).

    16× oversampled tone, noise LFSR, 32-step HW envelope, log ``voltTable``,
    DC high-pass and 1-pole low-pass. ``mix_div`` default 4 is the mixer
    ``1024/4096`` scale at volume 100. Recognizable, not analog-accurate.
    """

    def __init__(self, sample_rate: int, mix_div: int = 4):
        self.sr = sample_rate
        self.mix_div = mix_div if mix_div else 4
        # (1<<28) * 3579545 / 32 / sr  — same as AY8910.c BASE_PHASE_STEP.
        self.base_step = (1 << 28) * 3579545 // 32 // sample_rate
        self.reg = [0] * 16
        self.tone_phase = [0, 0, 0]
        self.tone_step = [1 << 31, 1 << 31, 1 << 31]
        self.noise_phase = 0
        self.noise_step = self.base_step
        self.noise_rand = 1
        self.noise_volume = 1
        self.env_shape = 0
        self.env_step = self.base_step // 8
        self.env_phase = 0
        self.enable = 0
        self.amp_volume = [0, 0, 0]
        self.ctrl_volume = 0
        self.old_sample = 0
        self.da_volume = 0

    def write(self, r: int, v: int) -> None:
        r &= 15
        v &= _AY_REG_MASK[r]
        self.reg[r] = v
        if r <= 5:
            period = self.reg[r & 6] | (self.reg[r | 1] << 8)
            self.tone_step[r >> 1] = (
                self.base_step // period if period else 1 << 31
            )
        elif r == 6:
            period = v if v else 1
            self.noise_step = self.base_step // period
        elif r == 7:
            self.enable = v
        elif r <= 10:
            self.amp_volume[r - 8] = v
        elif r <= 12:
            period = 16 * (self.reg[11] | (self.reg[12] << 8))
            self.env_step = self.base_step // (period if period else 8)
        elif r == 13:
            if v < 4:
                v = 0x09
            if v < 8:
                v = 0x0F
            self.env_shape = v
            self.env_phase = 0
            self.reg[13] = v

    def sample(self) -> int:
        sample_vol = [0, 0, 0]
        self.noise_phase = (self.noise_phase + self.noise_step) & 0xFFFFFFFF
        while self.noise_phase >> 28:
            self.noise_phase = (self.noise_phase - 0x10000000) & 0xFFFFFFFF
            self.noise_volume ^= ((self.noise_rand + 1) >> 1) & 1
            self.noise_rand = (
                (self.noise_rand ^ (0x28000 * (self.noise_rand & 1)))
                & 0xFFFFFFFF
            ) >> 1

        self.env_phase = (self.env_phase + self.env_step) & 0xFFFFFFFF
        if (self.env_shape & 1) and (self.env_phase >> 28):
            self.env_phase = 0x10000000
        env_volume = (self.env_phase >> 23) & 0x1F
        if (
            ((self.env_phase >> 27) & (self.env_shape + 1) ^ (~self.env_shape >> 1))
            & 2
        ):
            env_volume ^= 0x1F

        for ch in range(3):
            enable = self.enable >> ch
            noise_en = ((enable >> 3) | self.noise_volume) & 1
            phase_step = (~enable & 1) * self.tone_step[ch]
            tone_phase = self.tone_phase[ch]
            tone = 0
            for _ in range(16):
                tone_phase = (tone_phase + phase_step) & 0xFFFFFFFF
                tone += (enable | (tone_phase >> 31)) & noise_en
            self.tone_phase[ch] = tone_phase
            amp = self.amp_volume[ch]
            if amp & 0x10:
                sample_vol[ch] += tone * _AY_ENV_VOL[env_volume] // 16
            else:
                sample_vol[ch] += tone * AY_VOL[amp & 0x0F] // 16

        acc = sample_vol[0] + sample_vol[1] + sample_vol[2]
        self.ctrl_volume = (
            acc
            - self.old_sample
            + _tdiv(0x3FE7 * self.ctrl_volume, 0x4000)
        )
        self.old_sample = acc
        self.da_volume += _tdiv(2 * (self.ctrl_volume - self.da_volume), 3)
        out = _tdiv(9 * self.da_volume, self.mix_div)
        if out > 32767:
            return 32767
        if out < -32767:
            return -32767
        return out


class Channel:
    __slots__ = ("st", "slot", "psg_ch", "alive", "ea_hits")

    def __init__(self, slot: int, psg_ch: int, ptr: int):
        self.st = bytearray(TEMPLATE)
        self.st[0] = ptr & 0xFF
        self.st[1] = ptr >> 8
        self.slot = slot
        self.psg_ch = psg_ch
        self.alive = True
        self.ea_hits = 0

    def ptr(self) -> int:
        return self.st[0] | (self.st[1] << 8)

    def set_ptr(self, cpu: int) -> None:
        self.st[0] = cpu & 0xFF
        self.st[1] = cpu >> 8


class Driver:
    def __init__(self, rom: bytes, mapper: BankMap, tables: Tables):
        self.rom = rom
        self.mapper = mapper
        self.tables = tables
        self.mixer = 0xBC
        self.fade = 0  # C0A6
        self.live = 0x07  # C0A7 bits 0..2
        self.ay = None  # type: AY | None
        self.ch: list[Channel] = []

    def peek(self, cpu: int) -> int:
        return self.rom[self.mapper.cpu_off(cpu)]

    def peek16(self, cpu: int) -> int:
        return self.peek(cpu) | (self.peek((cpu + 1) & 0xFFFF) << 8)

    def note_period(self, idx: int) -> int:
        return self.peek16(self.tables.note_tbl + (idx & 0x0F) * 2)

    def wr(self, reg: int, val: int) -> None:
        assert self.ay is not None
        self.ay.write(reg, val)

    def wr_period(self, ch: Channel, period: int) -> None:
        self.wr(ch.psg_ch * 2, period & 0xFF)
        self.wr(ch.psg_ch * 2 + 1, (period >> 8) & 0x0F)

    def wr_vol(self, ch: Channel, vol: int) -> None:
        self.wr(8 + ch.psg_ch, vol & 0x1F)

    def mix_apply(self, ch: Channel, table: list[tuple[int, int]]) -> None:
        a, o = table[ch.psg_ch]
        self.mixer = (self.mixer & a) | o
        self.wr(7, self.mixer)

    def play(self, id80: int, sample_rate: int, loops: int, max_seconds: float, min_seconds: float):
        rec = self.tables.music_ptr + ((id80 & 0x7F) * 6)
        ptrs = [self.peek16(rec + i * 2) for i in range(3)]
        self.ay = AY(sample_rate)
        self.mixer = 0xBC
        self.fade = 0
        self.live = 0x07
        self.wr(7, self.mixer)
        self.ch = [Channel(i, i, ptrs[i]) for i in range(3)]

        spf = int(round(sample_rate / FRAME_HZ))
        max_frames = int(max_seconds * FRAME_HZ)
        fade_frames = int(FRAME_HZ)
        pcm = bytearray()
        stop_at = None  # type: int | None

        for frame in range(max_frames + fade_frames + 1):
            self.wr(7, self.mixer)
            for ch in self.ch:
                if ch.alive:
                    self.tick(ch)
            if stop_at is None:
                if self.live & 7 == 0:
                    stop_at = frame + fade_frames
                elif (
                    max(c.ea_hits for c in self.ch) >= loops
                    and frame > int(min_seconds * FRAME_HZ)
                ):
                    stop_at = frame + fade_frames
            gain = 1.0
            if stop_at is not None:
                left = stop_at - frame
                if left <= 0:
                    break
                if left < fade_frames:
                    gain = left / fade_frames
            for _ in range(spf):
                s = int(self.ay.sample() * gain)
                pcm.extend(struct.pack("<h", s))
        return bytes(pcm), ptrs

    def play_sfx(self, sid: int, sample_rate: int, max_seconds: float):
        """Solo sfx on PSG C (slot 3), matching play ids 1..N."""
        ptr = self.peek16(self.tables.sfx_ptr + sid * 2)
        self.ay = AY(sample_rate)
        self.mixer = 0xBF  # all muted; sfx mixer ops enable C
        self.fade = 0
        self.wr(7, self.mixer)
        ch = Channel(3, 2, 0)
        ch.st[12] = ptr & 0xFF
        ch.st[13] = ptr >> 8

        spf = int(round(sample_rate / FRAME_HZ))
        max_frames = int(max_seconds * FRAME_HZ)
        fade_frames = max(1, int(0.12 * FRAME_HZ))
        pcm = bytearray()
        stop_at = None  # type: int | None

        for frame in range(max_frames + fade_frames + 1):
            self.wr(7, self.mixer)
            if stop_at is None:
                if self.sfx_fetch(ch) or frame >= max_frames:
                    self.wr_vol(ch, 0)
                    stop_at = frame + fade_frames
            gain = 1.0
            if stop_at is not None:
                left = stop_at - frame
                if left <= 0:
                    break
                if left < fade_frames:
                    gain = left / fade_frames
            for _ in range(spf):
                s = int(self.ay.sample() * gain)
                pcm.extend(struct.pack("<h", s))
        return bytes(pcm), ptr

    def tick(self, ch: Channel) -> None:
        st = ch.st
        dur = st[9]
        dur = (dur - 1) & 0xFF
        st[9] = dur
        if dur == 0:
            self.fetch(ch)
            return
        flags = st[2]
        if flags & 1:
            # Pitched: decay / hold.
            if dur >= st[11]:
                self._decay_vol(ch)
                return
            if dur >= st[6]:
                return
            self._decay_vol(ch)
            return
        if flags & 0x80:
            return
        if self.sfx_fetch(ch):
            st[2] = flags | 0x80
            st[10] = 0
            self.wr_vol(ch, 0)

    def _decay_vol(self, ch: Channel) -> None:
        vol = ch.st[10]
        nxt = (vol - 1) & 0xFF
        if nxt & 0x80:
            return
        ch.st[10] = nxt
        self.wr_vol(ch, nxt)

    def fetch(self, ch: Channel) -> None:
        cpu = ch.ptr()
        for _ in range(4096):
            op = self.peek(cpu)
            cpu = (cpu + 1) & 0xFFFF
            if op < 0xD0:
                ch.set_ptr(cpu)
                if op >= 0xC0:
                    self._rest(ch, op)
                else:
                    self._note(ch, op)
                return
            cpu = self._command(ch, op, cpu)
            if not ch.alive:
                return
        raise RuntimeError("command loop at 0x%04X" % ch.ptr())

    def _duration(self, ch: Channel, op: int) -> int:
        n = (op & 0x0F) + 1
        scale = ch.st[3]
        acc = 0
        for _ in range(n):
            acc = (acc + scale) & 0xFF
        ch.st[9] = acc
        return acc

    def _rest(self, ch: Channel, op: int) -> None:
        self._duration(ch, op)
        ch.st[10] = 0
        self.wr_vol(ch, 0)

    def _note(self, ch: Channel, op: int) -> None:
        self._duration(ch, op)
        flags = ch.st[2]
        if flags & 1:
            ch.st[11] = (ch.st[9] - ch.st[5]) & 0xFF
            idx = op >> 4
            period = self.note_period(idx)
            srl = ch.st[7]
            steps = srl if srl else 256
            for _ in range(steps):
                period >>= 1
            if flags & 0x40:
                period = (period + 2) & 0xFFFF
            self.wr_period(ch, period)
            vol = (self.fade + ch.st[4]) & 0xFF
            if vol & 0x80:
                vol = 0
            ch.st[10] = vol
            self.wr_vol(ch, vol)
            self.mix_apply(ch, MIX_TONE)
            return
        table = self.tables.env_ptr_alt if (flags & 4) else self.tables.env_ptr
        env = self.peek16(table + ((op & 0xF0) >> 3))
        ch.st[12] = env & 0xFF
        ch.st[13] = env >> 8
        ch.st[2] = flags & 0x7F
        ch.st[14] = 1

    def _command(self, ch: Channel, op: int, cpu: int) -> int:
        hi = op & 0xF0
        lo = op & 0x0F
        if hi == 0xD0:
            ch.st[3] = lo
            return cpu
        if hi == 0xE0:
            return self._cmd_e(ch, lo, cpu)
        if lo == 0x0F:
            mask = 0x7F
            for _ in range(ch.slot + 1):
                mask = ((mask << 1) | (mask >> 7)) & 0xFF
            self.live &= mask
            ch.alive = False
            self.wr_vol(ch, 0)
            return cpu
        if lo == 0x0E:
            return self._loop(ch, cpu)
        # Envelope params (F0-FD except FE/FF handled above).
        ch.st[4] = (lo + 1) & 0xFF
        b = self.peek(cpu)
        cpu = (cpu + 1) & 0xFFFF
        ch.st[5] = ((b >> 4) - 1) & 0xFF
        ch.st[6] = b & 0x0F
        return cpu

    def _cmd_e(self, ch: Channel, lo: int, cpu: int) -> int:
        if lo < 6:
            ch.st[7] = (6 - lo) & 0xFF
            return cpu
        if lo == 6:
            return cpu  # sfx lock: ignore
        if lo == 7:
            ch.st[2] |= 0x40
            return cpu
        if lo == 0x0A:
            dest = self.peek16(cpu)
            ch.ea_hits += 1
            return dest
        if lo == 0x0B:
            return cpu  # unlock
        if lo == 0x0D:
            dest = self.peek16(cpu)
            ret = (cpu + 2) & 0xFFFF
            ch.st[0x12] = ret & 0xFF
            ch.st[0x13] = ret >> 8
            return dest
        if lo == 0x0E:
            return ch.st[0x12] | (ch.st[0x13] << 8)
        ch.st[2] = (ch.st[2] & 0xF8) | (lo & 7)
        return cpu

    def _loop(self, ch: Channel, cpu: int) -> int:
        n = (ch.st[0x10] - 1) & 0xFF
        if n == 0:
            ch.st[0x10] = 0
            return (cpu + 3) & 0xFFFF
        if n < 0x80:
            ch.st[0x10] = n
            return self.peek16(cpu + 1)
        count = self.peek(cpu)
        ch.st[0x10] = (count - 1) & 0xFF
        return self.peek16((cpu + 1) & 0xFFFF)

    def sfx_fetch(self, ch: Channel) -> bool:
        """True (CY) if the env/sfx stream ended."""
        st = ch.st
        d = (st[14] - 1) & 0xFF
        st[14] = d
        if d != 0:
            return False
        st[14] = st[15]
        cpu = st[12] | (st[13] << 8)
        for _ in range(256):
            b = self.peek(cpu)
            if b == 0xFF:
                return True
            cpu = (cpu + 1) & 0xFFFF
            if b == 0xFE:
                cpu = self._sfx_loop(ch, cpu)
                continue
            hi = b & 0xF0
            c = b
            if hi == 0x10:
                self.wr(6, (c & 0x0F) * 2)
                c = self.peek(cpu)
                cpu = (cpu + 1) & 0xFFFF
                hi = c & 0xF0
            if hi == 0x20:
                self._sfx_mix(ch, c)
                env_bit = (c << 1) & 0x10
                st[10] = env_bit
                # AY amp bit4 = use hardware envelope (not volume 0x0F).
                self.wr_vol(ch, env_bit)
                reload = self.peek(cpu)
                cpu = (cpu + 1) & 0xFFFF
                st[14] = reload
                st[15] = reload
                if c == 0x20:
                    st[12] = cpu & 0xFF
                    st[13] = cpu >> 8
                    return False
                if c < 0x28:
                    continue
                coarse = self.peek(cpu)
                cpu = (cpu + 1) & 0xFFFF
                fine = self.peek(cpu)
                cpu = (cpu + 1) & 0xFFFF
                self.wr(12, coarse)
                self.wr(11, fine)
                continue
            vol = c >> 4
            if st[10] & 0x10:
                self.wr(13, vol)  # envelope shape
            else:
                st[10] = vol
                self.wr_vol(ch, vol)
            period_hi = c & 0x0F
            period_lo = self.peek(cpu)
            cpu = (cpu + 1) & 0xFFFF
            st[12] = cpu & 0xFF
            st[13] = cpu >> 8
            self.wr_period(ch, period_lo | (period_hi << 8))
            return False
        return True

    def _sfx_loop(self, ch: Channel, cpu: int) -> int:
        n = (ch.st[0x11] - 1) & 0xFF
        if n == 0:
            ch.st[0x11] = 0
            return (cpu + 3) & 0xFFFF
        if n < 0x80:
            ch.st[0x11] = n
            return self.peek16(cpu + 1)
        count = self.peek(cpu)
        ch.st[0x11] = (count - 1) & 0xFF
        return self.peek16((cpu + 1) & 0xFFFF)

    def _sfx_mix(self, ch: Channel, c: int) -> None:
        if not (c & 1):
            if c & 2:
                self.mix_apply(ch, MIX_TONE)
            else:
                self.mix_apply(ch, MIX_MUTE)
        elif c & 2:
            self.mix_apply(ch, MIX_BOTH)
        else:
            self.mix_apply(ch, MIX_NOISE)


def write_wav(path: str, sr: int, pcm: bytes) -> None:
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)


def verify_note_tbl(rom: bytes, mapper: BankMap, note_tbl: int) -> None:
    off = mapper.cpu_off(note_tbl)
    got = [rom[off + i] | (rom[off + i + 1] << 8) for i in range(0, 24, 2)]
    if got != NOTE_PERIODS:
        sys.exit(
            "note table mismatch at 0x%04X: %s"
            % (note_tbl, ["%04X" % p for p in got])
        )


def parse_id_range(s: str) -> list[int]:
    if "-" not in s:
        return [int(s, 0)]
    a, b = s.split("-", 1)
    lo, hi = int(a, 0), int(b, 0)
    if hi < lo:
        raise argparse.ArgumentTypeError("empty id range %s" % s)
    return list(range(lo, hi + 1))


def parse_name(s: str) -> tuple[int, str]:
    if "=" not in s:
        raise argparse.ArgumentTypeError("--name wants ID=STEM, got %r" % s)
    k, v = s.split("=", 1)
    return int(k, 0), v


def run(
    rom: bytes,
    mapper: BankMap,
    tables: Tables,
    ids: list[int],
    *,
    sfx: bool = False,
    names: dict[int, str] | None = None,
    out_dir: str = ".",
    rate: int = 22050,
    loops: int = 2,
    min_seconds: float = 20.0,
    seconds: float | None = None,
    verify: bool = True,
) -> None:
    names = names or {}
    if verify:
        verify_note_tbl(rom, mapper, tables.note_tbl)
    cap = (4.0 if sfx else 90.0) if seconds is None else seconds
    for i in ids:
        drv = Driver(rom, mapper, tables)
        name = names.get(i, "%02X" % i)
        path = os.path.join(out_dir, name + ".wav")
        if sfx:
            pcm, ptr = drv.play_sfx(i, rate, cap)
            write_wav(path, rate, pcm)
            sec = len(pcm) / (2 * rate)
            print("0x%02X  %s  ptr=%04X  %.2fs  %s" % (i, name, ptr, sec, path))
        else:
            pcm, ptrs = drv.play(i, rate, max(1, loops), cap, min_seconds)
            write_wav(path, rate, pcm)
            sec = len(pcm) / (2 * rate)
            print(
                "0x%02X  %s  A/B/C=%04X/%04X/%04X  %.1fs  %s"
                % (i, name, ptrs[0], ptrs[1], ptrs[2], sec, path)
            )


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rom", help="ROM image")
    ap.add_argument(
        "--map",
        required=True,
        help="BANK@CPU windows (8 KiB), comma-separated, e.g. 2@8000,3@a000",
    )
    ap.add_argument("--music-ptr", type=lambda s: int(s, 0), required=True,
                    help="6-byte records (3 channel ptrs); id 0x80 is record 0")
    ap.add_argument("--sfx-ptr", type=lambda s: int(s, 0), required=True,
                    help="word table; SFX indexes id*2 (id 1 = first sfx)")
    ap.add_argument("--env-ptr", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--env-alt", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--note-tbl", type=lambda s: int(s, 0), required=True,
                    help="12 little-endian periods (one octave)")
    ap.add_argument("--sfx", action="store_true", help="render sfx instead of BGM")
    ap.add_argument("--id", type=lambda s: int(s, 0), help="single id")
    ap.add_argument("--music-ids", type=parse_id_range, help="BGM range, e.g. 0x80-0x8F")
    ap.add_argument("--sfx-ids", type=parse_id_range, help="sfx range, e.g. 1-0x10")
    ap.add_argument("--name", action="append", default=[], metavar="ID=STEM",
                    type=parse_name, help="output filename stem (repeatable)")
    ap.add_argument("--loops", type=int, default=2, help="EA-loop repeats before fade (BGM)")
    ap.add_argument("--min-seconds", type=float, default=20.0,
                    help="play at least this long if the track loops")
    ap.add_argument("--seconds", type=float, default=None,
                    help="hard cap (default 90 BGM / 4 sfx)")
    ap.add_argument("--rate", type=int, default=22050)
    ap.add_argument("-o", "--out", default=".")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip note-table sanity check")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.rom):
        sys.exit("no ROM: %s" % args.rom)
    try:
        mapper = BankMap.parse(args.map)
    except ValueError as e:
        sys.exit(str(e))
    tables = Tables(
        args.music_ptr, args.sfx_ptr, args.env_ptr, args.env_alt, args.note_tbl
    )
    if args.id is not None:
        ids = [args.id]
    elif args.sfx:
        if not args.sfx_ids:
            sys.exit("pass --id or --sfx-ids")
        ids = args.sfx_ids
    else:
        if not args.music_ids:
            sys.exit("pass --id or --music-ids")
        ids = args.music_ids
    names = dict(args.name)
    rom = open(args.rom, "rb").read()
    run(
        rom, mapper, tables, ids,
        sfx=args.sfx, names=names, out_dir=args.out, rate=args.rate,
        loops=args.loops, min_seconds=args.min_seconds, seconds=args.seconds,
        verify=not args.no_verify,
    )


if __name__ == "__main__":
    main()
