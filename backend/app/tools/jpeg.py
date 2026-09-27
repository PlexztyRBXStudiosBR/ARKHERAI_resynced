"""JPEG baseline luma (SOF0) sem PIL — arquivo .jpg de verdade, cena inteira."""
from __future__ import annotations

import math
import struct

_QT = [
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99,
]
_ZZ = [
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63,
]
_DC_N = [0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
_DC_V = list(range(12))
_AC_N = [0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 0x7D]
_AC_V = [
    0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06, 0x13, 0x51, 0x61, 0x07,
    0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08, 0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0,
    0x24, 0x33, 0x62, 0x72, 0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49,
    0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69,
    0x6A, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7,
    0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5,
    0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
    0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8,
    0xF9, 0xFA,
]


def _qt(quality: int) -> list[int]:
    q = max(1, min(100, quality))
    s = 5000 // q if q < 50 else 200 - q * 2
    return [max(1, min(255, (v * s + 50) // 100)) for v in _QT]


def _dct(blk: list[float]) -> list[float]:
    out = [0.0] * 64
    for u in range(8):
        for v in range(8):
            s = 0.0
            cu = 0.70710678 if u == 0 else 1.0
            cv = 0.70710678 if v == 0 else 1.0
            for y in range(8):
                for x in range(8):
                    s += blk[y * 8 + x] * math.cos((2 * x + 1) * u * math.pi / 16) * math.cos((2 * y + 1) * v * math.pi / 16)
            out[u + v * 8] = s * 0.25 * cu * cv
    return out


class _Bits:
    def __init__(self) -> None:
        self.b = bytearray()
        self.acc = 0
        self.n = 0

    def push(self, val: int, nbits: int) -> None:
        for i in range(nbits - 1, -1, -1):
            self.acc = (self.acc << 1) | ((val >> i) & 1)
            self.n += 1
            if self.n == 8:
                self.b.append(self.acc)
                if self.acc == 0xFF:
                    self.b.append(0)
                self.acc = 0
                self.n = 0

    def flush(self) -> bytes:
        if self.n:
            self.acc <<= 8 - self.n
            self.b.append(self.acc)
            if self.acc == 0xFF:
                self.b.append(0)
        return bytes(self.b)


def _cat(v: int) -> tuple[int, int]:
    if v == 0:
        return 0, 0
    a = abs(v)
    n = a.bit_length()
    return n, v if v > 0 else v + (1 << n) - 1


def _ht(ncounts: list[int], vals: list[int]) -> dict[int, tuple[int, int]]:
    ht: dict[int, tuple[int, int]] = {}
    code = 0
    k = 0
    for i, n in enumerate(ncounts):
        for _ in range(n):
            ht[vals[k]] = (code, i + 1)
            k += 1
            code += 1
        code <<= 1
    return ht


def encode_jpeg(w: int, h: int, rgb: bytes, quality: int = 78) -> bytes:
    dc_ht = _ht(_DC_N, _DC_V)
    ac_ht = _ht(_AC_N, _AC_V)
    qt = _qt(quality)
    bits = _Bits()
    prev_dc = 0
    bw = (w + 7) // 8 * 8
    bh = (h + 7) // 8 * 8

    def y_at(x: int, y: int) -> int:
        x = min(w - 1, max(0, x))
        y = min(h - 1, max(0, y))
        i = (y * w + x) * 3
        r, g, b = rgb[i], rgb[i + 1], rgb[i + 2]
        return int(0.299 * r + 0.587 * g + 0.114 * b)

    for by in range(0, bh, 8):
        for bx in range(0, bw, 8):
            blk = [float(y_at(bx + xx, by + yy) - 128) for yy in range(8) for xx in range(8)]
            coef = _dct(blk)
            zz = [max(-1023, min(1023, int(round(coef[i] / qt[i])))) for i in _ZZ]
            dc = zz[0] - prev_dc
            prev_dc = zz[0]
            n, code = _cat(dc)
            c, nb = dc_ht[n]
            bits.push(c, nb)
            if n:
                bits.push(code, n)
            zeros = 0
            last_nz = 0
            for i, ac in enumerate(zz[1:], start=1):
                if ac:
                    last_nz = i
            for i, ac in enumerate(zz[1:], start=1):
                if ac == 0:
                    zeros += 1
                    continue
                while zeros >= 16:
                    c, nb = ac_ht[0xF0]
                    bits.push(c, nb)
                    zeros -= 16
                n, code = _cat(ac)
                c, nb = ac_ht[(zeros << 4) | n]
                bits.push(c, nb)
                bits.push(code, n)
                zeros = 0
                if i == last_nz:
                    break
            if last_nz < 63:
                c, nb = ac_ht[0x00]
                bits.push(c, nb)
    scan = bits.flush()

    def mk(code: int, payload: bytes) -> bytes:
        return b"\xff" + bytes([code]) + struct.pack(">H", len(payload) + 2) + payload

    out = bytearray(b"\xff\xd8")
    out += mk(0xE0, b"JFIF\x00\x01\x02\x00\x00\x01\x00\x01\x00\x00")
    out += mk(0xDB, bytes([0x00]) + bytes(qt))
    out += mk(0xC0, struct.pack(">BHHB", 8, h, w, 1) + bytes([1, 0x11, 0]))
    out += mk(0xC4, bytes([0x00]) + bytes(_DC_N) + bytes(_DC_V))
    out += mk(0xC4, bytes([0x10]) + bytes(_AC_N) + bytes(_AC_V))
    out += mk(0xDA, bytes([1, 1, 0x00, 0, 63, 0]))
    out += scan
    out += b"\xff\xd9"
    return bytes(out)
