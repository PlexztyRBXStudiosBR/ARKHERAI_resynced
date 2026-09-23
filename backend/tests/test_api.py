"""Testes do backend ARKHER: health, auth, autorização, limites, modelo,
streaming, cancelamento, memória por usuário, ferramentas e logs sem segredos."""
from __future__ import annotations

import json
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


# ------------------------------------------------------ geradores game dev
def test_roblox_gen_exige_autorizacao(auth_client):
    r = auth_client.post("/api/tools/roblox_gen/run", json={"tipo": "leaderstats"})
    assert r.status_code == 403


def test_roblox_gen_produz_lua_valido(auth_client):
    auth_client.post("/api/tools/roblox_gen/authorize")
    r = auth_client.post("/api/tools/roblox_gen/run", json={"tipo": "salvamento"})
    assert r.status_code == 200
    codigo = r.json()["result"]["codigo"]
    assert "DataStoreService" in codigo and "PlayerAdded" in codigo


def test_roblox_gen_rejeita_tipo_invalido(auth_client):
    auth_client.post("/api/tools/roblox_gen/authorize")
    r = auth_client.post("/api/tools/roblox_gen/run", json={"tipo": "nao_existe"})
    assert r.status_code == 400


def test_obj_gen_produz_obj_valido(auth_client):
    auth_client.post("/api/tools/obj_gen/authorize")
    r = auth_client.post("/api/tools/obj_gen/run", json={"seed": 42})
    assert r.status_code == 200
    obj = r.json()["result"]["arquivo"]["conteudo"]
    verts = [l for l in obj.splitlines() if l.startswith("v ")]
    faces = [l for l in obj.splitlines() if l.startswith("f ")]
    assert len(verts) == 256 and len(faces) == 225
    # determinístico pela seed
    r2 = auth_client.post("/api/tools/obj_gen/run", json={"seed": 42})
    assert r2.json()["result"]["arquivo"]["conteudo"] == obj


# ------------------------------------------------------------ conector blender
def test_blender_scripts_gerados_compilam(auth_client):
    """Os scripts Blender gerados precisam ser Python válido (py_compile)."""
    import py_compile
    import tempfile
    from pathlib import Path

    auth_client.post("/api/tools/blender_gen/authorize")
    for cena in ("terreno", "cena", "personagem", "animacao"):
        r = auth_client.post("/api/tools/blender_gen/run", json={"cena": cena, "seed": 9})
        assert r.status_code == 200, r.text
        res = r.json()["result"]
        script = res["arquivo"]["conteudo"]
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(script)
            caminho = f.name
        py_compile.compile(caminho, doraise=True)  # syntax real verificada
        Path(caminho).unlink()
        assert "bpy" in script and "export_scene.gltf" in script
    # animação: keyframes + sequência de frames + textura procedural
    from backend.app.tools import blender_gen
    anim = blender_gen.gerar_script("animacao", 5)
    assert "keyframe_insert" in anim and "render(animation=True)" in anim
    assert "ShaderNodeTexNoise" in anim  # textura gerada, sem asset externo


def test_intencao_animacao_natural(auth_client):
    auth_client.post("/api/tools/blender_gen/authorize")
    ev = _feito_sse(auth_client, "crie uma animacao 3d com textura no blender")
    assert ev.get("kind") == "arquivo"
    assert ev["arquivo"]["nome"].startswith("animacao")


def test_blender_gen_rejeita_cena_invalida(auth_client):
    auth_client.post("/api/tools/blender_gen/authorize")
    r = auth_client.post("/api/tools/blender_gen/run", json={"cena": "nao_existe"})
    assert r.status_code == 400


def test_blender_gen_exige_autorizacao(auth_client):
    r = auth_client.post("/api/tools/blender_gen/run", json={"cena": "cena"})
    assert r.status_code == 403


def test_blender_executar_com_blender_instalado(tmp_path, monkeypatch):
    """Com um binário Blender (fake aqui), executar() roda e devolve zip base64."""
    import base64
    import os
    import stat
    from backend.app.tools import blender_gen

    fake = tmp_path / "blender"
    fake.write_text(
        "#!/bin/sh\nmkdir -p arkher_saida\necho GLB > arkher_saida/x.glb\necho ARKHER_OK\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("ARKHER_BLENDER", str(fake))
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        res = blender_gen.executar(blender_gen.gerar_script("cena", 1), "cena_seed1")
    finally:
        os.chdir(cwd)
    assert res is not None
    assert res["itens"] == ["x.glb"]
    assert base64.b64decode(res["conteudo_b64"])[:2] == b"PK"


# ------------------------------------------- construção ao vivo (plugin-ponte)
def test_build_militar_ops_e_render():
    import xml.etree.ElementTree as ET
    from backend.app.tools import build_gen, rbxlx_gen

    ops = build_gen.base_militar(5)
    assert len(ops) > 60
    for op in ops:
        assert op["op"] == "part"
        assert len(op["pos"]) == 3 and len(op["size"]) == 3 and len(op["cor"]) == 3
        assert all(s > 0 for s in op["size"])
    xml = rbxlx_gen.renderizar_ops(ops)
    raiz = ET.fromstring(xml)
    classes = [it.get("class") for it in raiz.iter("Item")]
    assert classes.count("Part") == len(ops)
    # determinismo
    assert build_gen.base_militar(5) == ops
    assert build_gen.base_militar(6) != ops


def test_fluxo_build_api(auth_client):
    auth_client.post("/api/tools/build_gen/authorize")
    r = auth_client.post("/api/build/start", json={"tema": "base do exercito brasileiro", "seed": 8})
    assert r.status_code == 200, r.text
    bid = r.json()["build_id"]
    prox = auth_client.get("/api/build/proximo").json()
    assert prox.get("build_id") == bid and len(prox["ops"]) > 60
    um = auth_client.get(f"/api/build/{bid}").json()
    assert "exercito" in um["tema"]
    p = auth_client.get("/api/build/plugin")
    assert p.status_code == 200
    assert "Construir agora" in p.text and "X-Arkher-Token" in p.text


def test_build_exige_autorizacao(auth_client):
    r = auth_client.post("/api/build/start", json={"tema": "militar"})
    assert r.status_code == 403


def test_comando_construir(auth_client):
    auth_client.post("/api/tools/build_gen/authorize")
    ev = _feito_sse(auth_client, "/construir base militar 5")
    assert ev.get("kind") == "arquivo"
    assert ev["arquivo"]["nome"] == "arkher_base_militar_seed5.rbxlx"
    assert ev["arquivo"]["conteudo"].startswith("<?xml")


def test_intencao_base_exercito(auth_client):
    auth_client.post("/api/tools/build_gen/authorize")
    ev = _feito_sse(auth_client, "crie uma base do exercito brasileiro no roblox studio")
    assert ev.get("kind") == "arquivo"
    assert ev["arquivo"]["nome"].endswith(".rbxlx")
    assert ev["arquivo"]["conteudo"].count("<Item class=\"Part\"") > 60


def test_compositor_aberto_sem_lista_fixa():
    """O compositor interpreta pedidos livres — estruturas + quantidades."""
    from backend.app.tools import build_gen

    assert build_gen.interpretar("3 torres e 2 casas") == {"torre": 3, "casa": 2}
    assert build_gen.interpretar("quatro árvores e um heliponto") == {"arvore": 4, "heliponto": 1}
    ops = build_gen.compor("construa uma vila com 4 casas e 3 árvores", 9)
    nomes = [o["nome"] for o in ops]
    assert sum(n.startswith("Casa") for n in nomes) >= 4 * 8  # paredes/teto/porta…
    assert sum(n == "Copa" for n in nomes) == 3
    assert build_gen.compor("construa uma vila com 4 casas e 3 árvores", 9) == ops
    import pytest as _pt
    with _pt.raises(ValueError):
        build_gen.compor("zzz qqq nada reconhecível", 1)


def test_build_pede_permissao_para_ponte(auth_client):
    ev = _feito_sse(auth_client, "construa uma base militar no roblox")
    assert ev.get("kind") == "erro"
    assert "permissão" in ev["content"]


def test_addon_blender_servido_e_compila(auth_client, tmp_path):
    import py_compile
    auth_client.post("/api/tools/build_gen/authorize")
    r = auth_client.get("/api/build/plugin-blender")
    assert r.status_code == 200
    assert "ARKHER Ponte" in r.text and "from_pydata" in r.text
    alvo = tmp_path / "addon.py"
    alvo.write_text(r.text)
    py_compile.compile(str(alvo), doraise=True)  # sintaxe Python válida


# ------------------------------------------------------- place nativo Roblox
def test_rbxlx_gerados_sao_xml_valido():
    """Todo place gerado precisa ser XML bem-formado no formato oficial."""
    import xml.etree.ElementTree as ET
    from backend.app.tools import rbxlx_gen

    for tipo in ("obby", "arena", "base"):
        res = rbxlx_gen.gerar_place(tipo, 7)
        xml = res["arquivo"]["conteudo"]
        raiz = ET.fromstring(xml)  # lança se inválido
        assert raiz.tag == "roblox"
        classes = [it.get("class") for it in raiz.iter("Item")]
        assert "Workspace" in classes and "Lighting" in classes
        assert "SpawnLocation" in classes
        assert res["arquivo"]["nome"] == f"arkher_{tipo}_seed7.rbxlx"
    # obby tem lava com script; determinismo por seed
    obby1 = rbxlx_gen.gerar_place("obby", 3)["arquivo"]["conteudo"]
    obby2 = rbxlx_gen.gerar_place("obby", 3)["arquivo"]["conteudo"]
    assert obby1 == obby2
    assert "class=\"Script\"" in obby1 and "Touched" in obby1


def test_rbxlx_rejeita_tipo_invalido(auth_client):
    auth_client.post("/api/tools/rbxlx_gen/authorize")
    r = auth_client.post("/api/tools/rbxlx_gen/run", json={"tipo": "x"})
    assert r.status_code == 400


def test_comando_place_entrega_arquivo(auth_client):
    auth_client.post("/api/tools/rbxlx_gen/authorize")
    ev = _feito_sse(auth_client, "/place arena 5")
    assert ev.get("kind") == "arquivo"
    assert ev["arquivo"]["nome"] == "arkher_arena_seed5.rbxlx"
    assert ev["arquivo"]["conteudo"].startswith("<?xml")


def test_intencao_obby_natural(auth_client):
    auth_client.post("/api/tools/rbxlx_gen/authorize")
    ev = _feito_sse(auth_client, "cria um obby pro roblox")
    assert ev.get("kind") == "arquivo"
    assert ev["arquivo"]["nome"].startswith("arkher_obby")


# ------------------------------------------------------- intenção natural
def _feito_sse(auth_client, mensagem):
    with auth_client.stream("POST", "/api/chat", json={"message": mensagem}) as r:
        texto = "".join(chunk for chunk in r.iter_text())
    evento = {}
    if "event: done" in texto:
        dado = texto.split("event: done\ndata: ", 1)[1].split("\n\n", 1)[0]
        evento = json.loads(dado)
    return evento


def test_intencao_blender_personagem(auth_client):
    auth_client.post("/api/tools/blender_gen/authorize")
    ev = _feito_sse(auth_client, "Crie um personagem 3D no Blender")
    assert ev.get("kind") == "arquivo"
    assert ev["arquivo"]["nome"].startswith("personagem")
    assert "import bpy" in ev["arquivo"]["conteudo"]


def test_intencao_terreno_montanhas(auth_client):
    auth_client.post("/api/tools/obj_gen/authorize")
    ev = _feito_sse(auth_client, "gere um terreno com montanhas seed 11")
    assert ev.get("kind") == "arquivo"
    assert ev["arquivo"]["nome"].endswith(".obj")


def test_intencao_roblox_salvamento(auth_client):
    auth_client.post("/api/tools/roblox_gen/authorize")
    ev = _feito_sse(auth_client, "faz um sistema de salvamento pro roblox")
    assert ev.get("kind") == "ferramenta"
    assert "```lua" in ev["content"]


def test_intencao_exige_autorizacao(auth_client):
    ev = _feito_sse(auth_client, "crie um personagem no blender")
    assert ev.get("kind") == "erro"
    assert "bloqueada" in ev["content"]


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
