from backend.app.chat import composer
from backend.tests.conftest import read_sse


def test_composer_responde_qualquer_coisa():
    r = composer.responder("oi")
    assert "ARKHER" in r
    assert "ponte" not in r.lower() or "Não preciso de ponte" in r


def test_composer_identidade():
    r = composer.responder("quem é você")
    assert "ARKHER" in r
    assert "Roblox" in r


def test_composer_matematica():
    r = composer.responder("2+3*4")
    assert "14" in r


def test_chat_pergunta_livre_sem_modelo(auth_client):
    with auth_client.stream("POST", "/api/chat", json={"message": "como funciona netcode em jogo online?"}) as r:
        text = "".join(r.iter_text())
    events = read_sse(text)
    done = [d for ev, d in events if ev == "done"]
    assert done
    assert "error" not in [ev for ev, _ in events]
    assert "servidor" in done[0]["content"].lower() or "netcode" in done[0]["content"].lower()


def test_textura_no_chat(auth_client):
    with auth_client.stream("POST", "/api/chat", json={"message": "crie uma textura de pedra"}) as r:
        text = "".join(r.iter_text())
    events = read_sse(text)
    done = [d for ev, d in events if ev == "done"]
    assert done and done[0].get("kind") == "arquivo"
    arq = done[0]["arquivo"]
    assert arq["nome"].endswith(".png")
    assert arq.get("conteudo_b64")
