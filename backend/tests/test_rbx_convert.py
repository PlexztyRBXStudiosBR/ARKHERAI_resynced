import struct
from pathlib import Path

from backend.app.acervo.convert import convert_bin, ingerir
from backend.app.acervo.rbx_binary import convert_file, dest_for, lz4_decompress, parse_binary, to_xml


def _zig(n: int) -> int:
    n = n & 0xFFFFFFFF
    if n >= 0x80000000:
        n -= 0x100000000
    return ((n << 1) ^ (n >> 31)) & 0xFFFFFFFF


def _i32be_interleaved(nums: list[int]) -> bytes:
    encoded = [_zig(n).to_bytes(4, "big") for n in nums]
    out = bytearray()
    for k in range(4):
        for e in encoded:
            out.append(e[k])
    return bytes(out)


def _pstr(s: str) -> bytes:
    b = s.encode()
    return struct.pack("<I", len(b)) + b


def _chunk(name: bytes, payload: bytes) -> bytes:
    name = (name + b"\x00\x00\x00\x00")[:4]
    return name + struct.pack("<III", 0, len(payload), 0) + payload


def _minimal_rbxl() -> bytes:
    # 1 classe Part, 1 instância id=1, pai raiz, Name=Floor
    header = b"<roblox!" + bytes.fromhex("89ff0d0a1a0a") + struct.pack("<Hii", 0, 1, 1) + b"\x00" * 8
    inst = (
        struct.pack("<I", 0)
        + _pstr("Part")
        + b"\x00"
        + struct.pack("<I", 1)
        + _i32be_interleaved([1])
    )
    prop = struct.pack("<I", 0) + _pstr("Name") + b"\x01" + _pstr("Floor")
    prnt = b"\x00" + struct.pack("<I", 1) + _i32be_interleaved([1]) + _i32be_interleaved([-1])
    end = b"</roblox>"
    return header + _chunk(b"INST", inst) + _chunk(b"PROP", prop) + _chunk(b"PRNT", prnt) + _chunk(b"END\x00", end)


def test_lz4_roundtrip_literals():
    # bloco só de literals (token 0x40 = 4 literals, match 0 but needs offset if more data)
    # "ABCD" as 4 literals then end: token 0x40 + ABCD
    raw = bytes([0x40]) + b"ABCD"
    assert lz4_decompress(raw, 4) == b"ABCD"


def test_converte_rbxl_minimo(tmp_path: Path):
    src = tmp_path / "mapa.rbxl"
    src.write_bytes(_minimal_rbxl())
    dst = convert_file(src)
    assert dst.suffix == ".rbxlx"
    text = dst.read_text(encoding="utf-8")
    assert 'class="Part"' in text
    assert "Floor" in text
    assert "referent=" in text


def test_converte_rbxm_extensao(tmp_path: Path):
    src = tmp_path / "npc.rbxm"
    src.write_bytes(_minimal_rbxl())
    assert dest_for(src).suffix == ".rbxmx"
    dst = convert_file(src)
    assert dst.name.endswith(".rbxmx")
    assert "Part" in dst.read_text(encoding="utf-8")


def test_xml_nao_e_renomeado(tmp_path: Path):
    src = tmp_path / "ja.rbxlx"
    src.write_text('<?xml version="1.0"?><roblox version="4"><Item class="Folder"/></roblox>', encoding="utf-8")
    dst = convert_file(src)
    assert dst == src


def test_lixo_binario_nao_vira_xml(tmp_path: Path):
    src = tmp_path / "jogo.rbxl"
    src.write_bytes(b"\x00nao-e-roblox")
    ok, msg = convert_bin(src, tmp_path / "jogo.rbxlx", "rbxl")
    assert ok is False
    assert "não é rbxl" in msg or "nao e" in msg.lower() or "ConvertError" in msg or "não é" in msg


def test_ingest_converte_binario(tmp_path: Path):
    root = tmp_path / "ArkherAITraining"
    root.mkdir()
    (root / "arena.rbxl").write_bytes(_minimal_rbxl())
    res = ingerir(root)
    assert res["ok"]
    rec = [a for a in res["arquivos"] if a["tipo"] == "rbxl"][0]
    assert rec["conversao"]["ok"] is True
    assert rec.get("xml") and str(rec["xml"]).endswith(".rbxlx")
    xml = Path(rec["xml"]).read_text(encoding="utf-8")
    assert "Part" in xml
