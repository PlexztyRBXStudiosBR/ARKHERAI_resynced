from backend.app.chat.service import _detectar_tarefa
from backend.app.studio import jogo, kits, provas


def test_jogo_inteiro_nao_e_obby():
    r = jogo.completo("praga", 9)
    xml = r["arquivo"]["conteudo"]
    assert "SpawnLocation" in xml
    assert "ObbyPad" not in xml
    assert len(r["pacote"]) >= 4
    hud = next(a["conteudo"] for a in r["pacote"] if "hud" in a["nome"])
    assert "Inter" not in hud and "Poppins" not in hud
    assert "UICorner" not in hud
    assert r["provas"]["ok"] is True


def test_provas_reprovam_ui_saas():
    xml = '<Item class="TextButton"/><Item class="UICorner"><int name="CornerRadius">16</int></Item><string>Inter</string>'
    u = provas.prova_ui(xml)
    assert u["ok"] is False
    assert any("IA" in f or "Inter" in f or "SaaS" in f for f in u["falhas"])


def test_kit_places_jogo():
    r = kits.gerar("places", "jogo", 3, "florida")
    assert r["arquivo"]["nome"].endswith(".rbxlx")
    assert r.get("provas")


def test_chat_pedido_jogo_inteiro():
    t = _detectar_tarefa("cria o jogo inteiro de stealth")
    assert t and t[0] == "jogo_completo"
