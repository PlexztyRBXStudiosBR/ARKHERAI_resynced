import importlib.util
from pathlib import Path

from backend.app.acervo import analise, ciclo, convert

_AGENT = Path(__file__).resolve().parents[2] / "workers" / "workspace" / "agent.py"
_spec = importlib.util.spec_from_file_location("arkher_agent", _AGENT)
ws_agent = importlib.util.module_from_spec(_spec)
assert _spec.loader
_spec.loader.exec_module(ws_agent)


def test_analise_rbxmx_e_rbxlx(tmp_path):
    xml = """<?xml version="1.0"?>
<roblox version="4">
  <Item class="Workspace"><Properties><string name="Name">Workspace</string></Properties>
    <Item class="Part"><Properties><string name="Name">Chao</string></Properties></Item>
    <Item class="Script"><Properties><string name="Name">Boot</string>
      <ProtectedString name="Source">print(1)</ProtectedString></Properties></Item>
    <Item class="RemoteEvent"><Properties><string name="Name">Hit</string></Properties></Item>
  </Item>
</roblox>
"""
    (tmp_path / "praga.rbxlx").write_text(xml, encoding="utf-8")
    (tmp_path / "jeep.rbxmx").write_text(xml.replace("Chao", "Jipe"), encoding="utf-8")
    out = tmp_path / "know"
    man = analise.analisar_pasta(tmp_path, out)
    assert man["novos"] == 2
    assert man["gigantes_100mb"] == 0
    shas = {p.stem for p in out.glob("*.json") if p.name != "manifest.json"}
    assert len(shas) == 2
    assert (out / "treino").exists()


def test_analise_nao_repete_hash(tmp_path):
    (tmp_path / "a.rbxlx").write_text("<roblox><Item class=\"Part\"/></roblox>", encoding="utf-8")
    out = tmp_path / "k"
    m1 = analise.analisar_pasta(tmp_path, out)
    ja = {pr["sha256"] for pr in m1["projects"]}
    m2 = analise.analisar_pasta(tmp_path, out, ja_visto=ja)
    assert m2["novos"] == 0
    assert m2["pulados_hash"] == 1


def test_scan_arquivo_grande_nao_explode(tmp_path, monkeypatch):
    monkeypatch.setattr(analise, "GRANDE", 50)
    monkeypatch.setattr(analise, "ENORME", 80)
    p = tmp_path / "florida.rbxlx"
    corpo = ('<Item class="Part"><string name="Name">bloco</string></Item>\n' * 20)
    p.write_text('<?xml version="1.0"?><roblox>' + corpo + "</roblox>", encoding="utf-8")
    item = analise.analisar_arquivo(p)
    assert item["grande"] is True
    assert item["modo"] == "blocos_1mb"
    assert item["instancias"] >= 1
    assert item["extractable"] is True


def test_binario_nao_e_fingido(tmp_path):
    p = tmp_path / "jogo.rbxl"
    p.write_bytes(b"\x00binary-roblox-place")
    item = analise.analisar_arquivo(p)
    assert item["extractable"] is False
    assert "binario" in item["format"]


def test_ciclo_conta_parametros_no_fim(tmp_path, monkeypatch):
    root = tmp_path / "ArkherAITraining"
    root.mkdir()
    (root / "mapa.rbxlx").write_text(
        '<?xml version="1.0"?><roblox><Item class="Workspace"/></roblox>', encoding="utf-8"
    )
    monkeypatch.setattr(ciclo, "KNOW", tmp_path / "know")
    monkeypatch.setattr("model.training.evolve.SEEN", tmp_path / "seen.json")
    res = ciclo.rodar(root, user_id="t", limite=10)
    assert res["ok"]
    assert res["analise"]["novos"] >= 1
    par = res["parametros"]
    assert par["params_agora"] > 0
    assert par["params_proximo"] >= 4_000_000
    assert "4e6" in par["formula"]
    assert par["gen_atual"] >= 1
    assert "pct" in par


def test_ingest_nao_duplica_grande(tmp_path, monkeypatch):
    monkeypatch.setattr(convert, "GRANDE", 40)
    root = tmp_path / "pack"
    root.mkdir()
    (root / "cidade.rbxlx").write_bytes(b"<?xml version='1.0'?><roblox>" + b"<Item class='Part'/>" * 8 + b"</roblox>")
    res = convert.ingerir(root)
    assert res["ok"]
    rec = res["arquivos"][0]
    assert rec["grande"] is True
    assert rec["conversao"]["mensagem"] == "xml_no_lugar"
    originais = list((root / "_arkher" / "originais").glob("*"))
    assert originais == []


def test_install_app_lista_fechada():
    r = ws_agent.install_app("chrome")
    assert r["ok"] is False
    assert "nao permitido" in r["message"] or "não permitido" in r["message"]
