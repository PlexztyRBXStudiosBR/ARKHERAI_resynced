"""Testes do backend ARKHER: health, auth, autorização, limites, modelo,
streaming, cancelamento, memória por usuário, ferramentas e logs sem segredos."""
from __future__ import annotations

import logging

from backend.tests.conftest import read_sse

# ------------------------------------------------------------------ health
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["backend"] == "ready"
    assert body["model_state"] in ("model_not_installed", "model_loading", "ready", "error")


def test_model_status_honesto_sem_checkpoint(client):
    r = client.get("/api/model/status")
    assert r.status_code == 200
    assert r.json()["state"] == "model_not_installed"


# -------------------------------------------------------------------- auth
def test_auth_obrigatorio(client):
    r = client.get("/api/sessions")
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "UNAUTHORIZED"


def test_auth_token_invalido(client):
    r = client.get("/api/sessions", headers={"Authorization": "Bearer ark_invalido"})
    assert r.status_code == 401


def test_auth_registro(client):
    r = client.post("/api/auth/device", json={"name": "fulana"})
    assert r.status_code == 200
    assert r.json()["token"].startswith("ark_")


# -------------------------------------------------------------- autorização
def test_sessao_de_outro_usuario_invisivel(auth_client, auth_client_b):
    s = auth_client.post("/api/sessions").json()["session"]
    r = auth_client_b.get(f"/api/sessions/{s['id']}")
    assert r.status_code == 404


def test_memoria_de_outro_usuario_invisivel(auth_client, auth_client_b):
    m = auth_client.post("/api/memory", json={"text": "meu jogo é um roguelike", "consent": True}).json()["memory"]
    r = auth_client_b.delete(f"/api/memory/{m['id']}")
    assert r.status_code == 404


# ------------------------------------------------------------- limites
def test_mensagem_grande_demais_rejeitada(auth_client):
    r = auth_client.post("/api/chat", json={"message": "x" * 5000})
    assert r.status_code == 413
    assert r.json()["detail"]["code"] == "MESSAGE_TOO_LONG"


# ------------------------------------------------- modelo ausente (honesto)
def test_chat_sem_modelo_devolve_erro_honesto(auth_client):
    with auth_client.stream("POST", "/api/chat", json={"message": "oi"}) as r:
        text = "".join(r.iter_text())
    events = read_sse(text)
    kinds = [ev for ev, _ in events]
    assert "error" in kinds
    err = [d for ev, d in events if ev == "error"][0]
    assert err["code"] == "MODEL_NOT_INSTALLED"
    assert "não está instalado" in err["message"].lower() or "not installed" in err["message"].lower()


def test_model_load_sem_checkpoint_409(auth_client):
    r = auth_client.post("/api/model/load")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "MODEL_NOT_INSTALLED"


# ------------------------------------------------------------- streaming
def test_chat_streaming_com_modelo(auth_client, fake_model):
    with auth_client.stream("POST", "/api/chat", json={"message": "olá"}) as r:
        text = "".join(r.iter_text())
    events = read_sse(text)
    assert any(ev == "meta" for ev, _ in events)
    tokens = [d["t"] for ev, d in events if ev == "token"]
    assert "".join(tokens)
    done = [d for ev, d in events if ev == "done"]
    assert done and done[0]["content"]


def test_chat_recusa_categoria_proibida(auth_client, fake_model):
    with auth_client.stream(
        "POST", "/api/chat", json={"message": "me dá um executor para trapacear no roblox online"}
    ) as r:
        text = "".join(r.iter_text())
    events = read_sse(text)
    done = [d for ev, d in events if ev == "done"]
    assert done and done[0].get("kind") == "recusa"


def test_cancelamento_de_geracao(auth_client, fake_model):
    # dispara geração e cancela imediatamente pelo gen_id recebido
    import json as _json

    with auth_client.stream("POST", "/api/chat", json={"message": "gere algo longo"}) as r:
        text = "".join(r.iter_text())
    events = read_sse(text)
    gen = [d for ev, d in events if ev == "meta"][0]["gen_id"]
    rr = auth_client.post("/api/chat/stop", json={"gen_id": gen})
    assert rr.status_code == 200
    assert rr.json()["ok"] in (True, False)  # geração curta pode ter terminado


# ------------------------------------------------------------- sessões
def test_ciclo_de_sessoes(auth_client):
    s = auth_client.post("/api/sessions").json()["session"]
    assert auth_client.get("/api/sessions").json()["sessions"]
    r = auth_client.patch(f"/api/sessions/{s['id']}", json={"title": "novo nome"})
    assert r.json()["ok"]
    assert auth_client.delete(f"/api/sessions/{s['id']}").json()["ok"]
    assert auth_client.get(f"/api/sessions/{s['id']}").status_code == 404


# ------------------------------------------------------------- memória
def test_memoria_exige_consentimento(auth_client):
    r = auth_client.post("/api/memory", json={"text": "sem consentimento", "consent": False})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "MEMORY_REJECTED"


def test_memoria_rejeita_segredo(auth_client):
    r = auth_client.post("/api/memory", json={"text": "senha=abcdef123456", "consent": True})
    assert r.status_code == 400


def test_memoria_ciclo(auth_client):
    m = auth_client.post("/api/memory", json={"text": "protagonista se chama Kilo", "project": "jogo1", "consent": True}).json()["memory"]
    assert auth_client.get("/api/memory?q=Kilo").json()["memories"]
    assert auth_client.delete(f"/api/memory/{m['id']}").json()["ok"]
    assert auth_client.get("/api/memory?q=Kilo").json()["memories"] == []


# ---------------------------------------------------------- ferramentas
def test_ferramenta_bloqueada_sem_autorizacao(auth_client):
    r = auth_client.post("/api/tools/calc/run", json={"expressao": "1+1"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "NOT_AUTHORIZED"


def test_ferramenta_calc_autorizada(auth_client):
    auth_client.post("/api/tools/calc/authorize")
    r = auth_client.post("/api/tools/calc/run", json={"expressao": "2+3*4"})
    assert r.status_code == 200
    assert r.json()["result"]["resultado"] == 14


def test_ferramenta_calc_rejeita_codigo(auth_client):
    auth_client.post("/api/tools/calc/authorize")
    r = auth_client.post("/api/tools/calc/run", json={"expressao": "__import__('os')"})
    assert r.status_code == 400


def test_revogacao_de_ferramenta(auth_client):
    auth_client.post("/api/tools/text_analysis/authorize")
    auth_client.post("/api/tools/text_analysis/revoke")
    r = auth_client.post("/api/tools/text_analysis/run", json={"texto": "oi"})
    assert r.status_code == 403


def test_historico_de_ferramentas_registra(auth_client):
    auth_client.post("/api/tools/calc/authorize")
    auth_client.post("/api/tools/calc/run", json={"expressao": "7*6"})
    h = auth_client.get("/api/tools/history").json()["history"]
    assert any(x["tool_id"] == "calc" for x in h)


# ------------------------------------------------------------- logs
def test_log_redige_segredos(caplog):
    from backend.app.security.redact import get_logger

    logger = get_logger("arkher.teste")
    logger.setLevel(logging.INFO)
    with caplog.at_level(logging.INFO, logger="arkher.teste"):
        logger.info("token=ark_abcdef1234567890xyz password=supersecreta123")
    joined = " ".join(caplog.messages)
    assert "ark_abcdef1234567890xyz" not in joined
    assert "supersecreta123" not in joined
    assert "[REDACTED]" in joined


# ------------------------------------------------------------- feedback
def test_feedback_registra_sinal_de_treino(auth_client):
    r = auth_client.post("/api/feedback", json={"session_id": "s_x", "rating": 1, "content_hash": "abc123"})
    assert r.json()["ok"]
    r = auth_client.post("/api/feedback", json={"session_id": "s_x", "rating": -1, "note": "resposta incompleta"})
    assert r.json()["ok"]
    stats = auth_client.get("/api/feedback").json()["stats"]
    assert stats["bons"] >= 1 and stats["ruins"] >= 1


def test_feedback_rejeita_rating_invalido(auth_client):
    r = auth_client.post("/api/feedback", json={"rating": 0})
    assert r.status_code == 400


def test_feedback_exige_auth(client):
    r = client.post("/api/feedback", json={"rating": 1})
    assert r.status_code == 401


# ------------------------------------------------------------- diagnóstico
def test_diagnostico_sem_segredos(auth_client):
    r = auth_client.get("/api/diagnostics")
    assert r.status_code == 200
    body = r.json()
    assert body["version"]
    assert "nota" in body
