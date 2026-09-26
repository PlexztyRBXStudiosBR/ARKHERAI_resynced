from backend.app.chat.service import _detectar_tarefa
from backend.app.tools import figma_gen
from model.training import professores


def test_figma_json_vira_hud():
    doc = {
        "document": {
            "children": [
                {"type": "FRAME", "name": "HUD"},
                {"type": "TEXT", "name": "Jogar"},
                {"type": "TEXT", "name": "Loja"},
            ]
        }
    }
    r = figma_gen.de_json(doc, 3)
    assert r["arquivo"]["nome"].endswith(".rbxmx")
    assert "Jogar" in r["arquivo"]["conteudo"]
    assert "ScreenGui" in r["arquivo"]["conteudo"]


def test_figma_sem_token_nao_inventa_arquivo_remoto():
    r = figma_gen.puxar("", "", 1)
    assert r["ok"] is False
    assert r["code"] == "SEM_TOKEN"
    assert r["modo"] == "kit_proprio"


def test_detectar_figma_e_web():
    t = _detectar_tarefa("cria o hud do figma https://www.figma.com/file/AbC123xyz/jogo")
    assert t and t[0] == "figma_gen"
    assert t[1]["file_key"] == "AbC123xyz"
    w = _detectar_tarefa("pesquisa terrain generation roblox")
    assert w and w[0] == "web_search"
    assert "terrain" in w[1]["consulta"]


def test_professores_nunca_vao_pro_chat(tmp_path, monkeypatch):
    monkeypatch.setattr(professores, "CHECKPOINT_DIR", tmp_path)
    monkeypatch.setattr(professores, "EXTRA", tmp_path / "extra")
    (tmp_path / "extra").mkdir()
    (tmp_path / "lixo.bin").write_bytes(b"not-a-torch-model")
    d = professores.listar()
    assert d["ok"]
    assert "nao entra no chat" in d["regra"].replace("é", "e").replace("É", "E") or "não entra" in d["regra"] or "nunca" in d["regra"].lower() or "só ensina" in d["regra"] or "so ensina" in d["regra"]
    for p in d["professores"]:
        assert p["chat"] is False
