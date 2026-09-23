"""Fluxo de conversa do ARKHER: validação, guardas, memória, modelo próprio e SSE.

Regras duras:
- somente o modelo próprio gera respostas de linguagem;
- sem modelo → erro honesto MODEL_NOT_INSTALLED (nunca resposta simulada);
- ferramentas passam pelo backend (autorização + auditoria);
- memória só entra no contexto se o usuário permitiu.
"""
from __future__ import annotations

import asyncio
import json
import re
import secrets
import threading
import time
from datetime import datetime, timezone

from backend.app import config
from backend.app.chat import knowledge
from backend.app.memory import service as memory_service
from backend.app.model import runtime as model_runtime
from backend.app.security import guard, ratelimit
from backend.app.storage import db
from backend.app.tools import registry as tools

_CANCELS: dict[str, threading.Event] = {}
_CANCEL_LOCK = threading.Lock()

MODEL_NOT_INSTALLED_MSG = "O modelo próprio do ARKHER ainda não está instalado neste servidor."
MODEL_LOADING_MSG = "O modelo próprio do ARKHER ainda está carregando. Tente novamente em instantes."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def new_session_id() -> str:
    return "s_" + secrets.token_hex(8)


def create_session(user_id: str, title: str = "Nova conversa") -> dict:
    sid = new_session_id()
    db.execute(
        "INSERT INTO sessions (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (sid, user_id, title.strip()[:80] or "Nova conversa", _now(), _now()),
    )
    return get_session(sid, user_id)


def get_session(sid: str, user_id: str) -> dict | None:
    rows = db.query(
        "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ? AND user_id = ?",
        (sid, user_id),
    )
    return dict(rows[0]) if rows else None


def list_sessions(user_id: str) -> list[dict]:
    rows = db.query(
        "SELECT id, title, created_at, updated_at FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    )
    return [dict(r) for r in rows]


def delete_session(sid: str, user_id: str) -> bool:
    db.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return db.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (sid, user_id)) > 0


def rename_session(sid: str, user_id: str, title: str) -> bool:
    return (
        db.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (title.strip()[:80], _now(), sid, user_id),
        )
        > 0
    )


def add_message(sid: str, role: str, content: str, kind: str = "texto") -> None:
    db.execute(
        "INSERT INTO messages (id, session_id, role, content, kind, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("msg_" + secrets.token_hex(8), sid, role, content, kind, _now()),
    )
    db.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), sid))


def truncate_from_last_user(sid: str) -> None:
    """Remove a última mensagem do usuário e tudo que veio depois (regenerar/editar)."""
    rows = db.query(
        "SELECT id, role FROM messages WHERE session_id = ? ORDER BY created_at", (sid,)
    )
    last_user_idx = None
    for i, r in enumerate(rows):
        if r["role"] == "user":
            last_user_idx = i
    if last_user_idx is None:
        return
    doomed = [r["id"] for r in rows[last_user_idx:]]
    for mid in doomed:
        db.execute("DELETE FROM messages WHERE id = ?", (mid,))


def session_messages(sid: str, user_id: str) -> list[dict]:
    rows = db.query(
        "SELECT m.role, m.content, m.kind, m.created_at FROM messages m "
        "JOIN sessions s ON s.id = m.session_id "
        "WHERE m.session_id = ? AND s.user_id = ? ORDER BY m.created_at",
        (sid, user_id),
    )
    return [dict(r) for r in rows]


def request_cancel(gen_id: str) -> bool:
    with _CANCEL_LOCK:
        ev = _CANCELS.get(gen_id)
    if ev is None:
        return False
    ev.set()
    return True


def _record_metric(user_id: str, sid: str, in_tok: int, out_tok: int, ms: int, outcome: str) -> None:
    db.execute(
        "INSERT INTO metrics (user_id, session_id, input_tokens, output_tokens, duration_ms, outcome, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, sid, in_tok, out_tok, ms, outcome, _now()),
    )


STOP_MARKERS = ("\nPERGUNTA:", "\nQUESTION:")


def _build_prompt(user_id: str, history: list[dict], message: str, memory_enabled: bool, prefixo: str = "") -> str:
    """Monta o prompt no MESMO formato usado no treino (PERGUNTA/RESPOSTA).

    O prompt de sistema do ARKHER (config.SYSTEM_PROMPT) é aplicado pelas
    camadas do backend — guardas de entrada/saída e ferramentas — porque o
    modelo pequeno responde melhor ao formato exato do dataset.
    """
    parts: list[str] = []
    if memory_enabled:
        mems = memory_service.search(user_id, message, limit=2)
        for m in mems:
            parts.append(f"MEMÓRIA AUTORIZADA: {m['text']}")
    pares = [m for m in history if m["kind"] in ("texto", "modelo", "ferramenta")][-config.HISTORY_TURNS:]
    for m in pares:
        if m["role"] == "user":
            parts.append(f"PERGUNTA: {m['content']}")
        else:
            conteudo = m["content"].split("\n\n_Camada de verificação")[0]
            parts.append(f"RESPOSTA: {conteudo}")
    parts.append(f"PERGUNTA: {message}")
    parts.append("RESPOSTA:" + (f" {prefixo}" if prefixo else ""))
    return "\n".join(parts)


_TOOL_CMDS = {
    "/calc": ("calc", "expressao"),
    "/texto": ("text_analysis", "texto"),
    "/ler": ("file_read", "nome"),
    "/exportar": ("data_export", None),
    "/memoria": ("memory_query", "q"),
}


def _run_tool_message(user_id: str, message: str) -> tuple[str, str, list[str]]:
    """Executa comando de ferramenta explícito. Retorna (resposta, kind, tools_ran)."""
    parts = message.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    tool_id, field = _TOOL_CMDS[cmd]
    args = {} if field is None else {field: arg}
    try:
        result = tools.run(user_id, tool_id, args)
        if tool_id == "data_export":
            return (
                "Exportação pronta. Use o botão de download na resposta para salvar seus dados.",
                "export",
                [tool_id],
            )
        if tool_id == "file_read":
            conteudo = result["conteudo"][:8000]
            return f"Conteúdo de `{result['nome']}` ({result['caracteres']} caracteres):\n\n```\n{conteudo}\n```", "ferramenta", [tool_id]
        return "Resultado da ferramenta `" + tool_id + "`:\n\n```json\n" + json.dumps(result, ensure_ascii=False, indent=1)[:6000] + "\n```", "ferramenta", [tool_id]
    except tools.ToolError as e:
        return f"Ferramenta bloqueada: {e.message}", "erro", []


def chat_stream(user_id: str, session_id: str | None, message: str, memory_enabled: bool, replace_last_user: bool = False):
    """Gerador síncrono de eventos SSE (executado em thread separada)."""
    gen_id = "g_" + secrets.token_hex(6)
    stop_event = threading.Event()
    with _CANCEL_LOCK:
        _CANCELS[gen_id] = stop_event
    try:
        # sessão
        sid = session_id
        if sid:
            if get_session(sid, user_id) is None:
                yield sse("error", {"ok": False, "code": "SESSION_NOT_FOUND", "message": "Conversa não encontrada."})
                return
        else:
            title = re.sub(r"\s+", " ", message)[:60] or "Nova conversa"
            sid = create_session(user_id, title)["id"]
        yield sse("meta", {"gen_id": gen_id, "session_id": sid})

        message = message.strip()
        if not message or len(message) > config.MAX_MESSAGE_CHARS:
            yield sse("error", {"ok": False, "code": "INVALID_MESSAGE", "message": "Mensagem vazia ou acima do limite."})
            return

        if replace_last_user:
            truncate_from_last_user(sid)
        add_message(sid, "user", message)

        # camada de segurança de entrada
        refusal = guard.check_input(message)
        if refusal:
            add_message(sid, "assistant", refusal, kind="recusa")
            for i in range(0, len(refusal), 24):
                if stop_event.is_set():
                    yield sse("done", {"content": "", "cancelled": True})
                    return
                yield sse("token", {"t": refusal[i:i + 24]})
            yield sse("done", {"content": refusal, "kind": "recusa"})
            return

        # comando de ferramenta explícito
        first_word = message.split(maxsplit=1)[0].lower()
        if first_word in _TOOL_CMDS:
            resposta, kind, ran = _run_tool_message(user_id, message)
            add_message(sid, "assistant", resposta, kind=kind)
            yield sse("token", {"t": resposta})
            yield sse("done", {"content": resposta, "kind": kind, "tools": ran})
            return

        # modelo próprio — sem fallback, sem simulação
        st = model_runtime.status()
        if st["state"] == "model_not_installed":
            yield sse("error", {"ok": False, "code": "MODEL_NOT_INSTALLED", "message": MODEL_NOT_INSTALLED_MSG})
            return
        if st["state"] in ("model_loading", "loading"):
            yield sse("error", {"ok": False, "code": "MODEL_LOADING", "message": MODEL_LOADING_MSG})
            return
        if st["state"] == "error":
            yield sse("error", {"ok": False, "code": "MODEL_ERROR", "message": f"O modelo próprio falhou ao carregar: {st.get('error', 'erro desconhecido')}"})
            return

        history = session_messages(sid, user_id)[:-1]  # última já é a mensagem atual
        prefixo = knowledge.answer_prefix(message)
        prompt = _build_prompt(user_id, history, message, memory_enabled, prefixo)

        t0 = time.monotonic()
        collected: list[str] = []
        if prefixo:
            collected.append(prefixo + " ")
            yield sse("token", {"t": prefixo + " "})
        try:
            for delta in model_runtime.generate(
                prompt,
                max_new_tokens=config.MAX_NEW_TOKENS,
                stop_event=stop_event,
                timeout_s=config.GEN_TIMEOUT_S,
            ):
                if stop_event.is_set():
                    break
                collected.append(delta)
                joined = "".join(collected)
                corte = None
                for mk in STOP_MARKERS:
                    pos = joined.find(mk)
                    if pos >= 0 and (corte is None or pos < corte):
                        corte = pos
                if corte is not None:
                    collected = [joined[:corte]]
                    stop_event.set()
                    break
                yield sse("token", {"t": delta})
        except RuntimeError as e:
            code = str(e)
            msg = {
                "MODEL_NOT_INSTALLED": MODEL_NOT_INSTALLED_MSG,
                "MODEL_LOADING": MODEL_LOADING_MSG,
            }.get(code, "Falha na geração do modelo próprio.")
            yield sse("error", {"ok": False, "code": code, "message": msg})
            return

        cancelled = stop_event.is_set()
        raw = "".join(collected).strip()
        if prefixo and not raw.lower().startswith(prefixo.lower()[:24]):
            # o prefixo vem da recuperação no conhecimento do próprio projeto;
            # junto com a continuação do modelo forma a resposta completa
            raw = f"{prefixo} {raw}".strip()
        if not raw:
            raw = "(o modelo próprio ainda não produziu texto útil para esta entrada — modelo em estado experimental)"
        history_now = session_messages(sid, user_id)
        final, _corrections = guard.check_output(raw, tools_ran=[])
        add_message(sid, "assistant", final, kind="modelo")
        ms = int((time.monotonic() - t0) * 1000)
        _record_metric(user_id, sid, len(prompt) // 4, len(final) // 4, ms, "cancelado" if cancelled else "ok")
        yield sse("done", {"content": final, "cancelled": cancelled, "metrics": {"ms": ms}})
    finally:
        with _CANCEL_LOCK:
            _CANCELS.pop(gen_id, None)


async def chat_stream_async(user_id: str, session_id: str | None, message: str, memory_enabled: bool, replace_last_user: bool = False):
    """Ponte async→thread: tokens em fila, sem bloquear o event loop."""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def producer() -> None:
        try:
            for ev in chat_stream(user_id, session_id, message, memory_enabled, replace_last_user):
                loop.call_soon_threadsafe(queue.put_nowait, ev)
        except Exception as e:  # falha real, nunca silenciosa
            loop.call_soon_threadsafe(
                queue.put_nowait,
                sse("error", {"ok": False, "code": "INTERNAL", "message": f"Erro interno: {type(e).__name__}"}),
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=producer, name="arkher-chat", daemon=True).start()
    while True:
        item = await queue.get()
        if item is None:
            return
        yield item
