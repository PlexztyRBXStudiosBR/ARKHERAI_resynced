"""Rotas da API própria do ARKHER (documentadas em docs/API.md)."""
from __future__ import annotations

import platform
import time

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pathlib import Path
from pydantic import BaseModel, Field

from backend.app import config
from backend.app import training as training_service
from backend.app.auth import service as auth
from backend.app.chat import feedback as feedback_service
from backend.app.chat import service as chat
from backend.app.memory import service as memory_service
from backend.app.model import runtime as model_runtime
from backend.app.security import ratelimit
from backend.app.storage import db
from backend.app.acervo import service as acervo_service
from backend.app.chat import dual
from backend.app.integrations import service as integ_service
from backend.app.studio import kits as studio_kits
from backend.app.workspace import pilot as workspace_pilot
from backend.app.tools import build_gen
from backend.app.tools import registry as tools
from backend.app.workspace import service as workspace_service

STARTED_AT = time.time()

router = APIRouter()


class DeviceIn(BaseModel):
    name: str = Field(default="usuário", max_length=60)


class ChatIn(BaseModel):
    # O limite real é aplicado manualmente em MAX_MESSAGE_CHARS (erro 413 honesto);
    # aqui vai um teto largo apenas para rejeitar abusos grosseiros.
    message: str = Field(min_length=1, max_length=8000)
    session_id: str | None = None
    memory_enabled: bool = True
    replace_last_user: bool = False


class StopIn(BaseModel):
    gen_id: str


class SessionRename(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class MemoryIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    project: str = Field(default="", max_length=80)
    consent: bool


class FeedbackIn(BaseModel):
    session_id: str = ""
    content_hash: str = ""
    rating: int = Field(ge=-1, le=1)
    note: str = Field(default="", max_length=400)


# ------------------------------------------------------------------ público
@router.get("/api/health")
def health():
    st = model_runtime.status()
    return {"ok": True, "backend": "ready", "model_state": st["state"], "version": config.VERSION}


@router.get("/api/version")
def version():
    return {"ok": True, "version": config.VERSION, "model": config.MODEL_NAME}


@router.get("/api/model/status")
def model_status():
    return {"ok": True, **model_runtime.status()}


@router.post("/api/model/load")
def model_load(user: dict = auth.CurrentUser):
    st = model_runtime.load(wait_seconds=2.0)
    if st["state"] == "model_not_installed":
        raise HTTPException(
            status_code=409,
            detail={"ok": False, "code": "MODEL_NOT_INSTALLED",
                    "message": "O modelo próprio do ARKHER ainda não está instalado neste servidor."},
        )
    return {"ok": True, **st}


# ------------------------------------------------------------------- auth
@router.post("/api/auth/device")
def register(body: DeviceIn):
    return {"ok": True, **auth.register_device(body.name)}


# ------------------------------------------------------------------- chat
@router.post("/api/chat")
async def chat_post(req: Request, body: ChatIn, user: dict = auth.CurrentUser):
    ratelimit.check(user["id"], "chat", config.RATE_CHAT_PER_MIN)
    if len(body.message) > config.MAX_MESSAGE_CHARS:
        raise HTTPException(
            status_code=413,
            detail={"ok": False, "code": "MESSAGE_TOO_LONG",
                    "message": f"Mensagem acima do limite de {config.MAX_MESSAGE_CHARS} caracteres."},
        )
    return StreamingResponse(
        chat.chat_stream_async(user["id"], body.session_id, body.message, body.memory_enabled, body.replace_last_user),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/chat/stop")
def chat_stop(body: StopIn, user: dict = auth.CurrentUser):
    ok = chat.request_cancel(body.gen_id)
    return {"ok": ok}


# --------------------------------------------------------------- sessões
@router.get("/api/sessions")
def sessions_list(user: dict = auth.CurrentUser):
    ratelimit.check(user["id"], "api", config.RATE_API_PER_MIN)
    return {"ok": True, "sessions": chat.list_sessions(user["id"])}


@router.post("/api/sessions")
def sessions_create(user: dict = auth.CurrentUser):
    return {"ok": True, "session": chat.create_session(user["id"])}


@router.get("/api/sessions/{sid}")
def session_get(sid: str, user: dict = auth.CurrentUser):
    s = chat.get_session(sid, user["id"])
    if s is None:
        raise HTTPException(status_code=404, detail={"ok": False, "code": "SESSION_NOT_FOUND", "message": "Conversa não encontrada."})
    return {"ok": True, "session": s, "messages": chat.session_messages(sid, user["id"])}


@router.patch("/api/sessions/{sid}")
def session_rename(sid: str, body: SessionRename, user: dict = auth.CurrentUser):
    if not chat.rename_session(sid, user["id"], body.title):
        raise HTTPException(status_code=404, detail={"ok": False, "code": "SESSION_NOT_FOUND", "message": "Conversa não encontrada."})
    return {"ok": True}


@router.delete("/api/sessions/{sid}")
def session_delete(sid: str, user: dict = auth.CurrentUser):
    if not chat.delete_session(sid, user["id"]):
        raise HTTPException(status_code=404, detail={"ok": False, "code": "SESSION_NOT_FOUND", "message": "Conversa não encontrada."})
    return {"ok": True}


# --------------------------------------------------------------- memória
@router.get("/api/memory")
def memory_list(q: str = "", project: str = "", user: dict = auth.CurrentUser):
    return {"ok": True, "memories": memory_service.list_for(user["id"], q=q, project=project)}


@router.post("/api/memory")
def memory_add(body: MemoryIn, user: dict = auth.CurrentUser):
    try:
        m = memory_service.add(user["id"], body.text, body.project, body.consent)
    except memory_service.MemoryRejected as e:
        raise HTTPException(status_code=400, detail={"ok": False, "code": "MEMORY_REJECTED", "message": str(e)})
    return {"ok": True, "memory": m}


@router.delete("/api/memory/{mid}")
def memory_delete(mid: str, user: dict = auth.CurrentUser):
    if not memory_service.remove(mid, user["id"]):
        raise HTTPException(status_code=404, detail={"ok": False, "code": "MEMORY_NOT_FOUND", "message": "Memória não encontrada."})
    return {"ok": True}


@router.delete("/api/memory")
def memory_clear(user: dict = auth.CurrentUser):
    n = memory_service.clear(user["id"])
    return {"ok": True, "deleted": n}


@router.get("/api/memory/export")
def memory_export(user: dict = auth.CurrentUser):
    return {"ok": True, "memories": memory_service.export(user["id"])}


# --------------------------------------------------------------- feedback
@router.post("/api/feedback")
def feedback_post(body: FeedbackIn, user: dict = auth.CurrentUser):
    if body.rating not in (-1, 1):
        raise HTTPException(status_code=400, detail={"ok": False, "code": "BAD_RATING", "message": "Use 1 ou -1."})
    feedback_service.add(user["id"], body.session_id, body.rating, body.note, body.content_hash)
    return {"ok": True}


@router.get("/api/feedback")
def feedback_get(user: dict = auth.CurrentUser):
    return {"ok": True, "stats": feedback_service.stats(user["id"]), "items": feedback_service.export(user["id"])}


# ------------------------------------------------------------- ferramentas
@router.get("/api/tools")
def tools_list(user: dict = auth.CurrentUser):
    out = []
    for t in tools.TOOLS.values():
        out.append({**t, "authorized": tools.is_authorized(user["id"], t["id"])})
    return {"ok": True, "tools": out}


@router.post("/api/tools/{tool_id}/authorize")
def tool_authorize(tool_id: str, user: dict = auth.CurrentUser):
    try:
        tools.authorize(user["id"], tool_id)
    except tools.ToolError as e:
        raise HTTPException(status_code=404, detail={"ok": False, "code": e.code, "message": e.message})
    return {"ok": True}


@router.post("/api/tools/{tool_id}/revoke")
def tool_revoke(tool_id: str, user: dict = auth.CurrentUser):
    tools.revoke(user["id"], tool_id)
    return {"ok": True}


@router.get("/api/tools/history")
def tools_history(user: dict = auth.CurrentUser):
    return {"ok": True, "history": tools.history(user["id"])}


@router.post("/api/tools/{tool_id}/run")
def tool_run(tool_id: str, args: dict = Body(default={}), user: dict = auth.CurrentUser):
    ratelimit.check(user["id"], "api", config.RATE_API_PER_MIN)
    try:
        result = tools.run(user["id"], tool_id, args)
    except tools.ToolError as e:
        status = 403 if e.code == "NOT_AUTHORIZED" else 400
        raise HTTPException(status_code=status, detail={"ok": False, "code": e.code, "message": e.message})
    return {"ok": True, "result": result}


@router.post("/api/tools/files")
def tool_upload(body: dict = Body(...), user: dict = auth.CurrentUser):
    if not tools.is_authorized(user["id"], "file_read"):
        raise HTTPException(status_code=403, detail={"ok": False, "code": "NOT_AUTHORIZED", "message": "Autorize a ferramenta de leitura primeiro."})
    try:
        info = tools.save_upload(user["id"], str(body.get("name", "")), str(body.get("content_b64", "")))
    except Exception:
        raise HTTPException(status_code=400, detail={"ok": False, "code": "INVALID_UPLOAD", "message": "Upload inválido."})
    return {"ok": True, "file": info}


# ------------------------------------------------------------- treinamento
@router.get("/api/training/status")
def training_status(user: dict = auth.CurrentUser):
    return {"ok": True, **training_service.status()}


@router.post("/api/training/start")
def training_start(body: dict = Body(...), user: dict = auth.CurrentUser):
    step = str(body.get("step", ""))
    try:
        return {"ok": True, **training_service.start(step)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"ok": False, "code": "BAD_STEP", "message": str(e)})
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail={"ok": False, "code": "BUSY", "message": str(e)})


@router.get("/api/training/log")
def training_log(step: str = "train", user: dict = auth.CurrentUser):
    return {"ok": True, "lines": training_service.tail(step)}


@router.get("/api/training/news")
def training_news(user: dict = auth.CurrentUser):
    """Eventos reais do treino (checkpoints/relatórios) — mais novo primeiro."""
    return {"ok": True, "news": training_service.news()}


# ------------------------------------------------- construção ao vivo (ponte)
class BuildStartIn(BaseModel):
    tema: str = Field(min_length=1, max_length=200)
    seed: int = Field(default=42, ge=0, le=999999)


_PLUGIN_PATH = Path(__file__).resolve().parent.parent / "tools" / "arkher_ponte.lua"


@router.post("/api/build/start")
def build_start(body: BuildStartIn, user: dict = auth.CurrentUser):
    if not tools.is_authorized(user["id"], "build_gen"):
        raise HTTPException(status_code=403, detail={
            "ok": False, "code": "NOT_AUTHORIZED",
            "message": "Autorize a ferramenta build_gen na tela Ferramentas.",
        })
    try:
        build = build_gen.criar_build(user["id"], body.tema, body.seed)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"ok": False, "code": "BAD_TEMA", "message": str(e)})
    return {"ok": True, "build_id": build["build_id"], "tema": build["tema"], "pecas": len(build["ops"])}


@router.get("/api/build/proximo")
def build_proximo(user: dict = auth.CurrentUser):
    """Plugin-ponte busca a construção mais recente do usuário."""
    b = build_gen.build_pendente(user["id"])
    if b is None:
        return {}
    return b


@router.get("/api/build/plugin")
def build_plugin(user: dict = auth.CurrentUser):
    return PlainTextResponse(_PLUGIN_PATH.read_text(encoding="utf-8"))


_PLUGIN_BLENDER_PATH = Path(__file__).resolve().parent.parent / "tools" / "arkher_ponte_blender.py"


@router.get("/api/build/plugin-blender")
def build_plugin_blender(user: dict = auth.CurrentUser):
    return PlainTextResponse(_PLUGIN_BLENDER_PATH.read_text(encoding="utf-8"))


@router.get("/api/build/{build_id}")
def build_get(build_id: str, user: dict = auth.CurrentUser):
    b = build_gen.obter_build(user["id"], build_id)
    if b is None:
        raise HTTPException(status_code=404, detail={"ok": False, "code": "NOT_FOUND", "message": "Build não encontrado."})
    return b


# ------------------------------------------------------- produto: prontidão
@router.get("/api/produto/status")
def produto_status(user: dict = auth.CurrentUser):
    """Checklist honesto: o que está pronto no produto e o que falta."""
    from backend.app.tools import blender_gen, build_gen, rbxlx_gen  # noqa: F401

    root = Path(__file__).resolve().parents[3]
    dist = root / "frontend" / "dist"
    manifesto = root / "model" / "datasets" / "externos" / "MANIFESTO.json"
    fontes_baixadas = 0
    if manifesto.exists():
        try:
            import json as _json
            fontes_baixadas = len(_json.loads(manifesto.read_text(encoding="utf-8")).get("fontes", {}))
        except Exception:
            fontes_baixadas = 0

    st = model_runtime.status()
    ckpt = root / "model" / "checkpoints" / "latest.pt"
    train_txt = root / "model" / "datasets" / "generated" / "train.txt"
    vocab = root / "model" / "tokenizer" / "vocab" / "bpe_v1.json"

    def _mb(p: Path) -> str:
        return f"{p.stat().st_size // (1024*1024)} MB" if p.exists() else "ausente"

    def _kb(p: Path) -> str:
        return f"{p.stat().st_size // 1024} KB" if p.exists() else "ausente"

    itens = [
        {
            "id": "interface",
            "nome": "Interface completa (chat, memória, ferramentas, treino, config, mobile)",
            "ok": (dist / "index.html").exists() and any((dist / "assets").glob("*.js")) if (dist / "assets").exists() else False,
            "detalhe": "Frontend build servido pelo backend.",
        },
        {
            "id": "modelo",
            "nome": "Modelo próprio carregado e respondendo",
            "ok": st["state"] == "ready",
            "detalhe": f"estado={st['state']} | checkpoint={_mb(ckpt)}",
        },
        {
            "id": "tokenizer",
            "nome": "Tokenizer próprio (BPE)",
            "ok": vocab.exists(),
            "detalhe": "vocab/bpe_v1.json" if vocab.exists() else "vocab ausente",
        },
        {
            "id": "dataset",
            "nome": "Corpus de treino montado (+ fontes externas licenciadas)",
            "ok": train_txt.exists() and train_txt.stat().st_size > 100000,
            "detalhe": f"train.txt {_kb(train_txt)} | fontes externas baixadas: {fontes_baixadas}",
        },
        {
            "id": "ferramentas",
            "nome": "Ferramentas com autorização e auditoria",
            "ok": len(tools.TOOLS) >= 8,
            "detalhe": f"{len(tools.TOOLS)} ferramentas: " + ", ".join(sorted(tools.TOOLS)),
        },
        {
            "id": "pontes",
            "nome": "Pontes de construção ao vivo (plugin Roblox Studio + addon Blender)",
            "ok": (root / "backend" / "app" / "tools" / "arkher_ponte.lua").exists()
            and (root / "backend" / "app" / "tools" / "arkher_ponte_blender.py").exists(),
            "detalhe": "Entregues em /api/build/plugin e /api/build/plugin-blender.",
        },
        {
            "id": "render",
            "nome": "Nós de render/treino na rede (Kaggle, Colab, Lightning, PC)",
            "ok": (root / "workers" / "render" / "render_node.py").exists()
            and (root / "workers" / "kaggle" / "arkher_render.ipynb").exists()
            and (root / "workers" / "kaggle" / "arkher_treino.ipynb").exists(),
            "detalhe": "workers/ prontos; execução acontece nas contas do dono.",
        },
        {
            "id": "deploy",
            "nome": "Produção sempre ligada (Docker/systemd + auto-recuperar)",
            "ok": (
                (root / "Dockerfile").exists()
                and (root / "docker-compose.yml").exists()
                and (root / "deploy" / "arkher.service").exists()
                and (root / "deploy" / "arkher-watchdog.sh").exists()
            ),
            "detalhe": "docker compose up --build; systemd Restart=always + vigia de saúde.",
        },
    ]
    prontos = sum(1 for i in itens if i["ok"])
    from model.training import linhagem as _linhagem

    lin = _linhagem.plano()
    return {
        "ok": True,
        "prontos": prontos,
        "total": len(itens),
        "pct_pack": lin["pct"],
        "linhagem": {
            "pct": lin["pct"],
            "gen_atual": lin["gen_atual"],
            "atual": lin["atual"],
            "proximo": lin["proximo"],
            "promover": lin["promover"],
            "params_agora_formula": lin["params_agora_formula"],
            "params_proximo_formula": lin["params_proximo_formula"],
            "regra": lin["regra"],
            "formula": lin["formula"],
        },
        "itens": itens,
        "fora_do_produto_por_decisao": [
            "provedores externos de IA no runtime (a ARKHER é própria; HF só como operário de treino)",
            "shell arbitrário exposto na interface (o agente do Workspace só aceita jobs permitidos)",
            "IPs públicos no Workspace (SSRF — só Tailscale 100.x e LAN)",
            "raspagem de web/vídeos sem licença declarada (treino só com fontes licenciadas)",
            "scripts de executor/trapaça para jogos online (prejudica outros jogadores)",
        ],
    }


@router.get("/api/cerebro/linhagem")
def cerebro_linhagem(user: dict = auth.CurrentUser):
    from model.training import linhagem as _linhagem

    return _linhagem.plano()


@router.get("/api/cerebro/professores")
def cerebro_professores(user: dict = auth.CurrentUser):
    from model.training import professores as _prof

    return _prof.listar()


# ------------------------------------------------------------- integrações
class IntegIn(BaseModel):
    token: str = Field(default="", max_length=400)


@router.get("/api/integrations")
def integrations_list(user: dict = auth.CurrentUser):
    return {"ok": True, "integrations": integ_service.listar(user["id"])}


@router.post("/api/integrations/{iid}/authorize")
def integrations_auth(iid: str, body: IntegIn | None = None, user: dict = auth.CurrentUser):
    try:
        token = (body.token if body else "") or ""
        return {"ok": True, **integ_service.authorize(user["id"], iid, token or None)}
    except KeyError:
        raise HTTPException(status_code=404, detail={"ok": False, "code": "UNKNOWN", "message": "Integração desconhecida."})


@router.post("/api/integrations/{iid}/revoke")
def integrations_revoke(iid: str, user: dict = auth.CurrentUser):
    integ_service.revoke(user["id"], iid)
    return {"ok": True}


# ------------------------------------------------------------- workspace (PC virtual)
class VmIn(BaseModel):
    name: str = Field(default="PC virtual", max_length=60)
    tailscale_ip: str = Field(min_length=7, max_length=45)
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class VmJobIn(BaseModel):
    kind: str = Field(min_length=1, max_length=40)
    args: dict = Field(default_factory=dict)


@router.get("/api/workspace")
def workspace_list(user: dict = auth.CurrentUser):
    return {"ok": True, "vms": workspace_service.listar(user["id"])}


@router.post("/api/workspace")
def workspace_create(body: VmIn, user: dict = auth.CurrentUser):
    try:
        vm = workspace_service.criar(user["id"], body.name, body.tailscale_ip, body.username, body.password)
    except workspace_service.WorkspaceError as e:
        raise HTTPException(status_code=400, detail={"ok": False, "code": e.code, "message": e.message})
    return {"ok": True, "vm": vm}


@router.delete("/api/workspace/{vid}")
def workspace_delete(vid: str, user: dict = auth.CurrentUser):
    if not workspace_service.apagar(user["id"], vid):
        raise HTTPException(status_code=404, detail={"ok": False, "code": "NOT_FOUND", "message": "PC virtual não encontrado."})
    return {"ok": True}


@router.get("/api/workspace/{vid}/health")
def workspace_health(vid: str, user: dict = auth.CurrentUser):
    if workspace_service.obter(user["id"], vid) is None:
        raise HTTPException(status_code=404, detail={"ok": False, "code": "NOT_FOUND", "message": "PC virtual não encontrado."})
    return workspace_service.health(user["id"], vid)


@router.post("/api/workspace/{vid}/autologon")
def workspace_autologon(vid: str, user: dict = auth.CurrentUser):
    try:
        return {"ok": True, **workspace_service.autologon(user["id"], vid)}
    except workspace_service.WorkspaceError as e:
        status = 404 if e.code == "NOT_FOUND" else 502
        raise HTTPException(status_code=status, detail={"ok": False, "code": e.code, "message": e.message})


@router.post("/api/workspace/{vid}/job")
def workspace_job(vid: str, body: VmJobIn, user: dict = auth.CurrentUser):
    try:
        return {"ok": True, "result": workspace_service.job(user["id"], vid, body.kind, body.args)}
    except workspace_service.WorkspaceError as e:
        status = 404 if e.code == "NOT_FOUND" else 400
        raise HTTPException(status_code=status, detail={"ok": False, "code": e.code, "message": e.message})


@router.get("/api/workspace/agent.py", response_class=PlainTextResponse)
def workspace_agent_src(user: dict = auth.CurrentUser):
    path = Path(__file__).resolve().parents[3] / "workers" / "workspace" / "agent.py"
    return PlainTextResponse(path.read_text(encoding="utf-8"))


@router.get("/api/workspace/{vid}/screen")
def workspace_screen(vid: str, user: dict = auth.CurrentUser):
    try:
        return {"ok": True, **workspace_service.screen(user["id"], vid)}
    except workspace_service.WorkspaceError as e:
        status = 404 if e.code == "NOT_FOUND" else 502
        raise HTTPException(status_code=status, detail={"ok": False, "code": e.code, "message": e.message})


class PilotIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@router.post("/api/workspace/{vid}/pilot")
def workspace_pilot_post(vid: str, body: PilotIn, user: dict = auth.CurrentUser):
    try:
        return workspace_pilot.piloto(user["id"], vid, body.message)
    except workspace_service.WorkspaceError as e:
        status = 404 if e.code == "NOT_FOUND" else 502
        raise HTTPException(status_code=status, detail={"ok": False, "code": e.code, "message": e.message})


# ------------------------------------------------------------- estúdio (abas de produção)
class StudioGenIn(BaseModel):
    tab: str = Field(min_length=1, max_length=40)
    recipe: str = Field(min_length=1, max_length=40)
    seed: int = Field(default=42, ge=0, le=999999)
    prompt: str = Field(default="", max_length=400)


@router.get("/api/studio/catalog")
def studio_catalog(user: dict = auth.CurrentUser):
    return {"ok": True, "tabs": studio_kits.CATALOGO}


@router.post("/api/studio/generate")
def studio_generate(body: StudioGenIn, user: dict = auth.CurrentUser):
    try:
        res = studio_kits.gerar(body.tab, body.recipe, body.seed, body.prompt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"ok": False, "code": "BAD_RECIPE", "message": str(e)})
    if res.get("arquivo") and res["arquivo"].get("conteudo"):
        res["dual"] = dual.guardar(user["id"], f"{body.tab}/{body.recipe} {body.prompt}", res["arquivo"])
    return {"ok": True, "result": res}


@router.get("/api/studio/vault")
def studio_vault(user: dict = auth.CurrentUser):
    return {"ok": True, "itens": studio_kits.listar_vault()}


# ------------------------------------------------------------- acervo Roblox (celular)
class AcervoIn(BaseModel):
    root: str = Field(default="/storage/emulated/0/ArkherAITraining", max_length=400)


@router.get("/api/acervo")
def acervo_get(root: str = "/storage/emulated/0/ArkherAITraining", user: dict = auth.CurrentUser):
    return acervo_service.status(root)


@router.post("/api/acervo/ingest")
def acervo_ingest(body: AcervoIn, user: dict = auth.CurrentUser):
    return acervo_service.ingerir(body.root)


class AcervoCicloIn(BaseModel):
    root: str = Field(default="/storage/emulated/0/ArkherAITraining", max_length=400)
    limite: int = Field(default=0, ge=0, le=5000)


@router.post("/api/acervo/ciclo")
def acervo_ciclo(body: AcervoCicloIn, user: dict = auth.CurrentUser):
    """Pack inteiro: hash → XML/análise → cofre → parâmetros da linhagem no fim."""
    return acervo_service.ciclo(body.root, user_id=user["id"], limite=body.limite)


@router.get("/api/acervo/cofres")
def acervo_cofres(root: str = "/storage/emulated/0/ArkherAITraining", user: dict = auth.CurrentUser):
    from backend.app.acervo import cofres as _cofres

    return _cofres.resumo(Path(root))


@router.get("/api/acervo/ler")
def acervo_ler(path: str, user: dict = auth.CurrentUser):
    return acervo_service.ler(path)


# ------------------------------------------------------------- diagnóstico
@router.get("/api/diagnostics")
def diagnostics(user: dict = auth.CurrentUser):
    rows = db.query("SELECT COUNT(*) AS n FROM metrics")
    return {
        "ok": True,
        "version": config.VERSION,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "uptime_s": int(time.time() - STARTED_AT),
        "model": model_runtime.status(),
        "geracoes_registradas": rows[0]["n"] if rows else 0,
        "feedback": feedback_service.stats(user["id"]),
        "nota": "Este diagnóstico não contém segredos nem conteúdo de conversas.",
    }
