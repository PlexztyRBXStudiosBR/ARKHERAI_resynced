"""Conversor Roblox binário → XML (rbxl/rbxm → rbxlx/rbxmx).

Formato versão 0 (rbx-dom / RobloxAPI spec). Stdlib. LZ4 em Python puro.
Chunk ZSTD: usa o programa `zstd` se estiver no PATH. Não inventa XML.
"""
from __future__ import annotations

import base64
import struct
import subprocess
import xml.sax.saxutils as sax
from pathlib import Path

MAGIC = b"<roblox!"
SIG = bytes.fromhex("89ff0d0a1a0a")
ZSTD_MAGIC = bytes.fromhex("28b52ffd")


class ConvertError(ValueError):
    pass


def _u32(b: bytes, i: int) -> tuple[int, int]:
    return struct.unpack_from("<I", b, i)[0], i + 4


def _str(b: bytes, i: int) -> tuple[bytes, int]:
    n, i = _u32(b, i)
    if n > len(b) - i:
        raise ConvertError("string truncada")
    return b[i : i + n], i + n


def lz4_decompress(src: bytes, dest_size: int) -> bytes:
    out = bytearray()
    i = 0
    n = len(src)
    while i < n:
        token = src[i]
        i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                if i >= n:
                    raise ConvertError("lz4: literal truncado")
                extra = src[i]
                i += 1
                lit += extra
                if extra != 255:
                    break
        if i + lit > n:
            raise ConvertError("lz4: literals além do bloco")
        out.extend(src[i : i + lit])
        i += lit
        if i >= n:
            break
        if i + 2 > n:
            raise ConvertError("lz4: offset truncado")
        offset = src[i] | (src[i + 1] << 8)
        i += 2
        if offset == 0 or offset > len(out):
            raise ConvertError("lz4: offset inválido")
        match = (token & 0x0F) + 4
        if (token & 0x0F) == 15:
            while True:
                if i >= n:
                    raise ConvertError("lz4: match truncado")
                extra = src[i]
                i += 1
                match += extra
                if extra != 255:
                    break
        for _ in range(match):
            out.append(out[-offset])
    if dest_size and len(out) < dest_size:
        raise ConvertError(f"lz4: {len(out)} < {dest_size}")
    return bytes(out[:dest_size] if dest_size else out)


def _zstd(src: bytes) -> bytes:
    from shutil import which

    zstd = which("zstd") or which("zstd.exe")
    if not zstd:
        raise ConvertError(
            "chunk ZSTD: instale o programa zstd no PATH. "
            "A maioria dos .rbxl antigos é LZ4 e não precisa disso."
        )
    r = subprocess.run([zstd, "-d", "--stdout"], input=src, capture_output=True, timeout=180)
    if r.returncode != 0 or not r.stdout:
        raise ConvertError("zstd falhou: " + (r.stderr.decode("utf-8", "replace")[-200:]))
    return r.stdout


def decompress_chunk(raw: bytes, uncompressed: int) -> bytes:
    if uncompressed == 0:
        return b""
    if not raw:
        raise ConvertError("chunk vazio")
    if raw.startswith(ZSTD_MAGIC):
        out = _zstd(raw)
        return out[:uncompressed] if uncompressed else out
    return lz4_decompress(raw, uncompressed)


def deinterleave(buf: bytes, count: int, width: int) -> list[bytes]:
    if count * width > len(buf):
        raise ConvertError("interleave truncado")
    return [bytes(buf[k * count + i] for k in range(width)) for i in range(count)]


def zigzag32(u: int) -> int:
    u &= 0xFFFFFFFF
    return (u >> 1) ^ (-(u & 1))


def zigzag64(u: int) -> int:
    u &= 0xFFFFFFFFFFFFFFFF
    return (u >> 1) ^ (-(u & 1))


def rfloat_from_u32(u: int) -> float:
    bits = ((u >> 1) & 0x7FFFFFFF) | ((u & 1) << 31)
    return struct.unpack(">f", struct.pack(">I", bits))[0]


def read_interleaved_i32(data: bytes, i: int, count: int) -> tuple[list[int], int]:
    blob = data[i : i + count * 4]
    i += count * 4
    return [zigzag32(int.from_bytes(x, "big")) for x in deinterleave(blob, count, 4)], i


def read_interleaved_u32(data: bytes, i: int, count: int) -> tuple[list[int], int]:
    blob = data[i : i + count * 4]
    i += count * 4
    return [int.from_bytes(x, "big") for x in deinterleave(blob, count, 4)], i


def read_interleaved_rfloat(data: bytes, i: int, count: int) -> tuple[list[float], int]:
    blob = data[i : i + count * 4]
    i += count * 4
    return [rfloat_from_u32(int.from_bytes(x, "big")) for x in deinterleave(blob, count, 4)], i


def read_referents(data: bytes, i: int, count: int) -> tuple[list[int], int]:
    deltas, i = read_interleaved_i32(data, i, count)
    acc = 0
    refs = []
    for d in deltas:
        acc += d
        refs.append(acc)
    return refs, i


_CF_IDS: dict[int, tuple[float, ...]] = {
    1: (1, 0, 0, 0, 1, 0, 0, 0, 1),
    2: (1, 0, 0, 0, 0, -1, 0, 1, 0),
    3: (1, 0, 0, 0, -1, 0, 0, 0, -1),
    4: (1, 0, 0, 0, 0, 1, 0, -1, 0),
    5: (0, 1, 0, 1, 0, 0, 0, 0, -1),
    6: (0, 0, 1, 1, 0, 0, 0, 1, 0),
    7: (0, -1, 0, 1, 0, 0, 0, 0, 1),
    8: (0, 0, -1, 1, 0, 0, 0, -1, 0),
    9: (0, 1, 0, 0, 0, 1, 1, 0, 0),
    10: (0, 0, -1, 0, 1, 0, 1, 0, 0),
    11: (0, -1, 0, 0, 0, -1, 1, 0, 0),
    12: (0, 0, 1, 0, -1, 0, 1, 0, 0),
    13: (-1, 0, 0, 0, 1, 0, 0, 0, -1),
    14: (-1, 0, 0, 0, 0, 1, 0, 1, 0),
    15: (-1, 0, 0, 0, -1, 0, 0, 0, 1),
    16: (-1, 0, 0, 0, 0, -1, 0, -1, 0),
    17: (0, 1, 0, -1, 0, 0, 0, 0, 1),
    18: (0, 0, 1, -1, 0, 0, 0, -1, 0),
    19: (0, -1, 0, -1, 0, 0, 0, 0, -1),
    20: (0, 0, -1, -1, 0, 0, 0, 1, 0),
    21: (0, 1, 0, 0, 0, -1, -1, 0, 0),
    22: (0, 0, -1, 0, -1, 0, -1, 0, 0),
    23: (0, -1, 0, 0, 0, 1, -1, 0, 0),
    24: (0, 0, 1, 0, 1, 0, -1, 0, 0),
    25: (1, 0, 0, 0, 0, 1, 0, -1, 0),
    26: (0, 0, -1, 0, 1, 0, 1, 0, 0),
    27: (-1, 0, 0, 0, 0, -1, 0, -1, 0),
    28: (0, 0, 1, 0, -1, 0, 1, 0, 0),
    29: (0, 1, 0, 0, 0, 1, 1, 0, 0),
    30: (0, -1, 0, 0, 0, -1, 1, 0, 0),
    31: (0, 0, -1, 1, 0, 0, 0, 1, 0),
    32: (0, 0, 1, -1, 0, 0, 0, 1, 0),
    33: (0, 1, 0, 1, 0, 0, 0, 0, -1),
    34: (0, -1, 0, -1, 0, 0, 0, 0, 1),
    35: (1, 0, 0, 0, -1, 0, 0, 0, -1),
    36: (-1, 0, 0, 0, 1, 0, 0, 0, -1),
}


class _Buf:
    def __init__(self, data: bytes):
        self.d = data
        self.i = 0

    def take(self, n: int) -> bytes:
        if self.i + n > len(self.d):
            raise ConvertError("buffer curto")
        s = self.d[self.i : self.i + n]
        self.i += n
        return s


def _decode_prop(typ: int, count: int, buf: _Buf, shared: list[bytes]) -> list:
    d = buf.d
    if typ == 0x01:
        vals = []
        for _ in range(count):
            raw, buf.i = _str(d, buf.i)
            vals.append(raw)
        return vals
    if typ == 0x02:
        return [bool(x) for x in buf.take(count)]
    if typ == 0x03:
        vals, buf.i = read_interleaved_i32(d, buf.i, count)
        return vals
    if typ == 0x04:
        vals, buf.i = read_interleaved_rfloat(d, buf.i, count)
        return vals
    if typ == 0x05:
        vals = []
        for _ in range(count):
            v = struct.unpack_from("<d", d, buf.i)[0]
            buf.i += 8
            vals.append(v)
        return vals
    if typ == 0x06:
        sc, buf.i = read_interleaved_rfloat(d, buf.i, count)
        off, buf.i = read_interleaved_i32(d, buf.i, count)
        return list(zip(sc, off))
    if typ == 0x07:
        sx, buf.i = read_interleaved_rfloat(d, buf.i, count)
        ox, buf.i = read_interleaved_i32(d, buf.i, count)
        sy, buf.i = read_interleaved_rfloat(d, buf.i, count)
        oy, buf.i = read_interleaved_i32(d, buf.i, count)
        return list(zip(sx, ox, sy, oy))
    if typ == 0x08:
        vals = []
        for _ in range(count):
            nums = struct.unpack_from("<ffffff", d, buf.i)
            buf.i += 24
            vals.append(nums)
        return vals
    if typ in (0x09, 0x0A):
        return list(buf.take(count))
    if typ == 0x0B:
        vals, buf.i = read_interleaved_u32(d, buf.i, count)
        return vals
    if typ == 0x0C:
        r, buf.i = read_interleaved_rfloat(d, buf.i, count)
        g, buf.i = read_interleaved_rfloat(d, buf.i, count)
        b, buf.i = read_interleaved_rfloat(d, buf.i, count)
        return list(zip(r, g, b))
    if typ == 0x0D:
        x, buf.i = read_interleaved_rfloat(d, buf.i, count)
        y, buf.i = read_interleaved_rfloat(d, buf.i, count)
        return list(zip(x, y))
    if typ == 0x0E:
        x, buf.i = read_interleaved_rfloat(d, buf.i, count)
        y, buf.i = read_interleaved_rfloat(d, buf.i, count)
        z, buf.i = read_interleaved_rfloat(d, buf.i, count)
        return list(zip(x, y, z))
    if typ == 0x0F:
        vals = []
        for _ in range(count):
            x, y = struct.unpack_from("<hh", d, buf.i)
            buf.i += 4
            vals.append((x, y))
        return vals
    if typ in (0x10, 0x11):
        ids = list(buf.take(count))
        extra = sum(1 for t in ids if t == 0)
        matrices: list[tuple[float, ...]] = []
        if extra:
            comps = []
            for _ in range(9):
                col, buf.i = read_interleaved_rfloat(d, buf.i, extra)
                comps.append(col)
            ei = 0
            for t in ids:
                if t == 0:
                    matrices.append(tuple(comps[k][ei] for k in range(9)))
                    ei += 1
                else:
                    matrices.append(_CF_IDS.get(int(t), _CF_IDS[1]))
        else:
            matrices = [_CF_IDS.get(int(t), _CF_IDS[1]) for t in ids]
        px, buf.i = read_interleaved_rfloat(d, buf.i, count)
        py, buf.i = read_interleaved_rfloat(d, buf.i, count)
        pz, buf.i = read_interleaved_rfloat(d, buf.i, count)
        return list(zip(px, py, pz, matrices))
    if typ == 0x12:
        vals, buf.i = read_interleaved_u32(d, buf.i, count)
        return vals
    if typ == 0x13:
        refs, buf.i = read_referents(d, buf.i, count)
        return refs
    if typ == 0x14:
        vals = []
        for _ in range(count):
            x, y, z = struct.unpack_from("<hhh", d, buf.i)
            buf.i += 6
            vals.append((x, y, z))
        return vals
    if typ == 0x15:
        vals = []
        for _ in range(count):
            n, buf.i = _u32(d, buf.i)
            kps = []
            for _k in range(n):
                t, v, e = struct.unpack_from("<fff", d, buf.i)
                buf.i += 12
                kps.append((t, v, e))
            vals.append(kps)
        return vals
    if typ == 0x16:
        vals = []
        for _ in range(count):
            n, buf.i = _u32(d, buf.i)
            kps = []
            for _k in range(n):
                t, r, g, b, env = struct.unpack_from("<fffff", d, buf.i)
                buf.i += 20
                kps.append((t, r, g, b, env))
            vals.append(kps)
        return vals
    if typ == 0x17:
        vals = []
        for _ in range(count):
            a, b_ = struct.unpack_from("<ff", d, buf.i)
            buf.i += 8
            vals.append((a, b_))
        return vals
    if typ == 0x18:
        minx, buf.i = read_interleaved_rfloat(d, buf.i, count)
        miny, buf.i = read_interleaved_rfloat(d, buf.i, count)
        maxx, buf.i = read_interleaved_rfloat(d, buf.i, count)
        maxy, buf.i = read_interleaved_rfloat(d, buf.i, count)
        return list(zip(minx, miny, maxx, maxy))
    if typ == 0x19:
        vals = []
        for _ in range(count):
            custom = buf.take(1)[0]
            if custom:
                nums = struct.unpack_from("<fffff", d, buf.i)
                buf.i += 20
                vals.append((True,) + nums)
            else:
                vals.append((False,))
        return vals
    if typ == 0x1A:
        raw = buf.take(count * 3)
        return [(raw[i * 3] / 255, raw[i * 3 + 1] / 255, raw[i * 3 + 2] / 255) for i in range(count)]
    if typ == 0x1B:
        blob = buf.take(count * 8)
        return [zigzag64(int.from_bytes(x, "big")) for x in deinterleave(blob, count, 8)]
    if typ == 0x1C:
        idxs, buf.i = read_interleaved_u32(d, buf.i, count)
        return [shared[ix] if 0 <= ix < len(shared) else b"" for ix in idxs]
    if typ == 0x1E:
        flags = list(buf.take(count))
        present = sum(1 for f in flags if f)
        if present:
            cf = _decode_prop(0x10, present, buf, shared)
        else:
            cf = []
        it = iter(cf)
        return [next(it) if f else None for f in flags]
    if typ == 0x1F:
        idx, buf.i = read_interleaved_u32(d, buf.i, count)
        time_, buf.i = read_interleaved_u32(d, buf.i, count)
        blob = buf.take(count * 8)
        rnd = [int.from_bytes(x, "big") for x in deinterleave(blob, count, 8)]
        return list(zip(idx, time_, rnd))
    if typ == 0x20:
        vals = []
        for _ in range(count):
            fam, buf.i = _str(d, buf.i)
            w = struct.unpack_from("<H", d, buf.i)[0]
            buf.i += 2
            st = d[buf.i]
            buf.i += 1
            face, buf.i = _str(d, buf.i)
            vals.append((fam, w, st, face))
        return vals
    raise ConvertError(f"tipo de propriedade 0x{typ:02X} não suportado")


def _xml_text(s: str) -> str:
    return sax.escape(s, {"\"": "&quot;"})


def _fmt_f(v: float) -> str:
    if v != v:  # NaN
        return "0"
    s = f"{v:.6g}"
    return s


def _bytes_to_str(raw: bytes) -> str:
    return raw.decode("utf-8", errors="surrogateescape")


def _prop_xml(typ: int, name: str, value) -> str:
    n = _xml_text(name)
    if typ == 0x01 or typ == 0x1C:
        raw: bytes = value if isinstance(value, (bytes, bytearray)) else str(value).encode()
        if name in ("Source", "LinkedSource"):
            text = _bytes_to_str(bytes(raw))
            return f'<ProtectedString name="{n}"><![CDATA[{text.replace("]]>", "]]]]><![CDATA[>")}]]></ProtectedString>'
        if name in ("AttributesSerialize", "Tags", "PhysicsGrid", "SmoothGrid", "MaterialColors"):
            b64 = base64.b64encode(raw).decode("ascii")
            return f'<BinaryString name="{n}"><![CDATA[{b64}]]></BinaryString>'
        text = _bytes_to_str(bytes(raw))
        return f'<string name="{n}">{_xml_text(text)}</string>'
    if typ == 0x02:
        return f'<bool name="{n}">{"true" if value else "false"}</bool>'
    if typ in (0x03, 0x1B):
        return f'<int name="{n}">{int(value)}</int>' if typ == 0x03 else f'<int64 name="{n}">{int(value)}</int64>'
    if typ == 0x04:
        return f'<float name="{n}">{_fmt_f(float(value))}</float>'
    if typ == 0x05:
        return f'<double name="{n}">{_fmt_f(float(value))}</double>'
    if typ == 0x06:
        sc, off = value
        return f'<UDim name="{n}"><S>{_fmt_f(sc)}</S><O>{int(off)}</O></UDim>'
    if typ == 0x07:
        sx, ox, sy, oy = value
        return (
            f'<UDim2 name="{n}"><XS>{_fmt_f(sx)}</XS><XO>{int(ox)}</XO>'
            f"<YS>{_fmt_f(sy)}</YS><YO>{int(oy)}</YO></UDim2>"
        )
    if typ == 0x08:
        ox, oy, oz, dx, dy, dz = value
        return (
            f'<Ray name="{n}"><origin><X>{_fmt_f(ox)}</X><Y>{_fmt_f(oy)}</Y><Z>{_fmt_f(oz)}</Z></origin>'
            f"<direction><X>{_fmt_f(dx)}</X><Y>{_fmt_f(dy)}</Y><Z>{_fmt_f(dz)}</Z></direction></Ray>"
        )
    if typ == 0x09:
        return f'<Faces name="{n}">{int(value)}</Faces>'
    if typ == 0x0A:
        return f'<Axes name="{n}">{int(value)}</Axes>'
    if typ == 0x0B:
        return f'<int name="{n}">{int(value)}</int>'
    if typ in (0x0C, 0x1A):
        r, g, b = value
        return f'<Color3 name="{n}"><R>{_fmt_f(r)}</R><G>{_fmt_f(g)}</G><B>{_fmt_f(b)}</B></Color3>'
    if typ == 0x0D:
        x, y = value
        return f'<Vector2 name="{n}"><X>{_fmt_f(x)}</X><Y>{_fmt_f(y)}</Y></Vector2>'
    if typ == 0x0E:
        x, y, z = value
        return f'<Vector3 name="{n}"><X>{_fmt_f(x)}</X><Y>{_fmt_f(y)}</Y><Z>{_fmt_f(z)}</Z></Vector3>'
    if typ == 0x0F:
        x, y = value
        return f'<Vector2int16 name="{n}"><X>{int(x)}</X><Y>{int(y)}</Y></Vector2int16>'
    if typ in (0x10, 0x11):
        if value is None:
            return ""
        px, py, pz, m = value
        rows = "".join(f"<R{k // 3}{k % 3}>{_fmt_f(m[k])}</R{k // 3}{k % 3}>" for k in range(9))
        return (
            f'<CoordinateFrame name="{n}"><X>{_fmt_f(px)}</X><Y>{_fmt_f(py)}</Y><Z>{_fmt_f(pz)}</Z>'
            f"{rows}</CoordinateFrame>"
        )
    if typ == 0x12:
        return f'<token name="{n}">{int(value)}</token>'
    if typ == 0x13:
        if int(value) < 0:
            return f'<Ref name="{n}">null</Ref>'
        return f'<Ref name="{n}">RBX{int(value)}</Ref>'
    if typ == 0x14:
        x, y, z = value
        return f'<Vector3int16 name="{n}"><X>{int(x)}</X><Y>{int(y)}</Y><Z>{int(z)}</Z></Vector3int16>'
    if typ == 0x15:
        kps = "".join(
            f"<float>{_fmt_f(t)}</float><float>{_fmt_f(v)}</float><float>{_fmt_f(e)}</float>" for t, v, e in value
        )
        return f'<NumberSequence name="{n}">{kps}</NumberSequence>'
    if typ == 0x16:
        kps = "".join(
            f"<float>{_fmt_f(t)}</float><float>{_fmt_f(r)}</float><float>{_fmt_f(g)}</float>"
            f"<float>{_fmt_f(b)}</float><float>{_fmt_f(env)}</float>"
            for t, r, g, b, env in value
        )
        return f'<ColorSequence name="{n}">{kps}</ColorSequence>'
    if typ == 0x17:
        a, b_ = value
        return f'<NumberRange name="{n}">{_fmt_f(a)} {_fmt_f(b_)}</NumberRange>'
    if typ == 0x18:
        a, b_, c, d_ = value
        return (
            f'<Rect2D name="{n}"><min><X>{_fmt_f(a)}</X><Y>{_fmt_f(b_)}</Y></min>'
            f"<max><X>{_fmt_f(c)}</X><Y>{_fmt_f(d_)}</Y></max></Rect2D>"
        )
    if typ == 0x19:
        if not value or not value[0]:
            return f'<PhysicalProperties name="{n}"><CustomPhysics>false</CustomPhysics></PhysicalProperties>'
        _, dens, fr, el, fw, ew = value
        return (
            f'<PhysicalProperties name="{n}"><CustomPhysics>true</CustomPhysics>'
            f"<Density>{_fmt_f(dens)}</Density><Friction>{_fmt_f(fr)}</Friction>"
            f"<Elasticity>{_fmt_f(el)}</Elasticity><FrictionWeight>{_fmt_f(fw)}</FrictionWeight>"
            f"<ElasticityWeight>{_fmt_f(ew)}</ElasticityWeight></PhysicalProperties>"
        )
    if typ == 0x1E:
        if value is None:
            return ""
        return _prop_xml(0x10, name, value)
    if typ == 0x1F:
        idx, time_, rnd = value
        return f'<UniqueId name="{n}">{int(idx):08x}{int(time_):08x}{int(rnd) & 0xFFFFFFFFFFFFFFFF:016x}</UniqueId>'
    if typ == 0x20:
        fam, w, st, face = value
        return (
            f'<Font name="{n}"><Family>{_xml_text(_bytes_to_str(fam))}</Family>'
            f"<Weight>{int(w)}</Weight><Style>{int(st)}</Style>"
            f"<CachedFaceId>{_xml_text(_bytes_to_str(face))}</CachedFaceId></Font>"
        )
    return ""


def parse_binary(data: bytes) -> dict:
    if data.lstrip()[:7] == b"<roblox" and not data.lstrip().startswith(MAGIC):
        raise ConvertError("já é XML")
    if not data.startswith(MAGIC):
        raise ConvertError("não é rbxl/rbxm binário (falta <roblox!)")
    if len(data) < 32:
        raise ConvertError("cabeçalho curto")
    version = struct.unpack_from("<H", data, 14)[0]
    n_class = struct.unpack_from("<i", data, 16)[0]
    n_inst = struct.unpack_from("<i", data, 20)[0]
    if data[8:14] != SIG:
        # alguns arquivos velhos usam 4 bytes de assinatura; ainda tentamos
        pass
    if version not in (0,):
        raise ConvertError(f"versão binária {version} não suportada")
    i = 32
    classes: dict[int, dict] = {}
    instances: dict[int, dict] = {}
    shared: list[bytes] = []
    parents: dict[int, int] = {}
    while i + 16 <= len(data):
        name = data[i : i + 4]
        clen = struct.unpack_from("<I", data, i + 4)[0]
        ulen = struct.unpack_from("<I", data, i + 8)[0]
        i += 16
        if clen == 0:
            payload = data[i : i + ulen]
            i += ulen
        else:
            raw = data[i : i + clen]
            i += clen
            payload = decompress_chunk(raw, ulen)
        if name in (b"END\x00", b"END "):
            break
        if name == b"SSTR":
            _ver, j = _u32(payload, 0)
            n, j = _u32(payload, j)
            shared = []
            for _ in range(n):
                j += 16  # md5
                s, j = _str(payload, j)
                shared.append(s)
            continue
        if name == b"INST":
            cid = struct.unpack_from("<I", payload, 0)[0]
            cname, j = _str(payload, 4)
            has_svc = payload[j]
            j += 1
            n, j = _u32(payload, j)
            refs, j = read_referents(payload, j, n)
            if has_svc:
                j += n
            cls = cname.decode("utf-8", "replace")
            classes[cid] = {"name": cls, "refs": refs}
            for r in refs:
                instances[r] = {"class": cls, "id": r, "props": []}
            continue
        if name == b"PROP":
            cid = struct.unpack_from("<I", payload, 0)[0]
            pname, j = _str(payload, 4)
            typ = payload[j]
            j += 1
            info = classes.get(cid)
            if not info:
                continue
            buf = _Buf(payload)
            buf.i = j
            try:
                vals = _decode_prop(typ, len(info["refs"]), buf, shared)
            except ConvertError:
                continue
            pname_s = pname.decode("utf-8", "replace")
            for ref, val in zip(info["refs"], vals):
                inst = instances.get(ref)
                if inst is None:
                    continue
                xml = _prop_xml(typ, pname_s, val)
                if xml:
                    inst["props"].append(xml)
            continue
        if name == b"PRNT":
            j = 1
            n, j = _u32(payload, j)
            children, j = read_referents(payload, j, n)
            pars, j = read_referents(payload, j, n)
            for c, p in zip(children, pars):
                parents[c] = p
            continue
    children_of: dict[int, list[int]] = {-1: []}
    for inst_id in instances:
        children_of.setdefault(inst_id, [])
    for c, p in parents.items():
        children_of.setdefault(p, []).append(c)
    for lst in children_of.values():
        lst.sort()
    return {
        "n_class": n_class,
        "n_inst": n_inst,
        "instances": instances,
        "children_of": children_of,
    }


def _emit_item(inst_id: int, tree: dict, indent: int) -> str:
    inst = tree["instances"].get(inst_id)
    if not inst:
        return ""
    pad = "\t" * indent
    parts = [f'{pad}<Item class="{_xml_text(inst["class"])}" referent="RBX{inst_id}">']
    parts.append(f"{pad}\t<Properties>")
    for p in inst["props"]:
        parts.append(f"{pad}\t\t{p}")
    parts.append(f"{pad}\t</Properties>")
    for ch in tree["children_of"].get(inst_id, []):
        parts.append(_emit_item(ch, tree, indent + 1))
    parts.append(f"{pad}</Item>")
    return "\n".join(parts)


def to_xml(tree: dict) -> str:
    roots = tree["children_of"].get(-1, [])
    if not roots:
        # sem PRNT: tudo na raiz
        roots = sorted(tree["instances"])
    body = "\n".join(_emit_item(r, tree, 1) for r in roots)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">\n'
        "\t<External>null</External>\n"
        "\t<External>nil</External>\n"
        f"{body}\n"
        "</roblox>\n"
    )


def dest_for(src: Path) -> Path:
    ext = src.suffix.lower()
    if ext == ".rbxl":
        return src.with_suffix(".rbxlx")
    if ext == ".rbxm":
        return src.with_suffix(".rbxmx")
    if ext in (".rbxlx", ".rbxmx"):
        return src
    raise ConvertError(f"extensão não é Roblox: {src.suffix}")


def convert_file(src: Path, dst: Path | None = None) -> Path:
    src = Path(src)
    if not src.is_file():
        raise ConvertError(f"arquivo inexistente: {src}")
    raw = src.read_bytes()
    stripped = raw.lstrip()
    dst = Path(dst) if dst else dest_for(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if stripped.startswith(b"<") and not stripped.startswith(MAGIC):
        if dst.resolve() != src.resolve():
            dst.write_bytes(raw)
        return dst
    tree = parse_binary(raw)
    if not tree["instances"]:
        raise ConvertError("nenhuma instância no arquivo")
    dst.write_text(to_xml(tree), encoding="utf-8")
    return dst


def convert_many(paths: list[Path], recursive: bool = False) -> list[dict]:
    files: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            files.extend(
                x
                for x in it
                if x.is_file() and x.suffix.lower() in (".rbxl", ".rbxm", ".rbxlx", ".rbxmx")
            )
        elif p.is_file():
            files.append(p)
    out = []
    for f in files:
        rec = {"arquivo": str(f), "ok": False, "saida": "", "erro": ""}
        try:
            d = convert_file(f)
            rec["ok"] = True
            rec["saida"] = str(d)
        except ConvertError as e:
            rec["erro"] = str(e)
        except Exception as e:  # noqa: BLE001
            rec["erro"] = f"{type(e).__name__}: {e}"
        out.append(rec)
    return out
