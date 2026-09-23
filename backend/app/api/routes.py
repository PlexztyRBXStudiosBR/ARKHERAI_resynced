"""Rotas da API própria do ARKHER (documentadas em docs/API.md)."""
from __future__ import annotations

import platform
import time

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import StreamingResponse
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
from backend.app.tools import registry as tools

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
