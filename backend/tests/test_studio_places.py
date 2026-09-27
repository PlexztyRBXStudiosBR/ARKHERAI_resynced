import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("studio_places", ROOT / "tools" / "studio_places.py")
sp = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(sp)


def test_instala_rbxl_e_rbxlx_nao_rbxm(tmp_path: Path):
    pack = tmp_path / "ArkherAITraining"
    (pack / "mapas").mkdir(parents=True)
    (pack / "pendencias").mkdir()
    (pack / "mapas" / "arena.rbxlx").write_text("<roblox/>", encoding="utf-8")
    (pack / "mapas" / "bin.rbxl").write_bytes(b"x" * 80)
    (pack / "mapas" / "modelo.rbxm").write_bytes(b"m" * 80)
    (pack / "pendencias" / "falha.rbxlx").write_text("<roblox/>", encoding="utf-8")
    dest = tmp_path / "Places"
    res = sp.instalar([pack], dest)
    assert res["ok"]
    assert res["n"] == 2
    assert res["rbxlx"] == 1
    assert res["rbxl"] == 1
    nomes = {p.name for p in dest.iterdir() if p.suffix}
    assert "arena.rbxlx" in nomes
    assert "bin.rbxl" in nomes
    assert "modelo.rbxm" not in nomes
    assert "falha.rbxlx" not in nomes
