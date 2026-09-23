"""Memória própria do ARKHER: por usuário, com consentimento e controle total.

Busca textual local (sem embeddings externos). Nunca armazena tokens/senhas:
a camada de redação rejeita conteúdo com cara de segredo.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone

from backend.app.storage import db

_SECRETISH = re.compile(
    r"(?i)(senha|password|token|api[_-]?key|secret|chave\s+de\s+acesso)\s*[:=]\s*\S+"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryRejected(Exception):
    pass


def add(user_id: str, text: str, project: str, consent: bool) -> dict:
    text = text.strip()
    if not consent:
        raise MemoryRejected("Memória só é salva com consentimento explícito.")
    if not text or len(text) > 1000:
        raise MemoryRejected("Texto da memória vazio ou maior que 1000 caracteres.")
    if _SECRETISH.search(text):
        raise MemoryRejected("A ARKHER não guarda senhas, tokens ou segredos na memória.")
    mid = "m_" + secrets.token_hex(6)
    db.execute(
        "INSERT INTO memories (id, user_id, text, project, created_at) VALUES (?, ?, ?, ?, ?)",
        (mid, user_id, text, (project or "").strip()[:80], _now()),
    )
    return get(mid, user_id)


def get(mid: str, user_id: str) -> dict | None:
    rows = db.query(
        "SELECT id, text, project, created_at FROM memories WHERE id = ? AND user_id = ?",
        (mid, user_id),
    )
    return dict(rows[0]) if rows else None


def list_for(user_id: str, q: str = "", project: str = "") -> list[dict]:
    sql = "SELECT id, text, project, created_at FROM memories WHERE user_id = ?"
    params: list = [user_id]
    if q:
        sql += " AND text LIKE ?"
        params.append(f"%{q}%")
    if project:
        sql += " AND project = ?"
        params.append(project)
    sql += " ORDER BY created_at DESC LIMIT 500"
    return [dict(r) for r in db.query(sql, tuple(params))]


def remove(mid: str, user_id: str) -> bool:
    return db.execute("DELETE FROM memories WHERE id = ? AND user_id = ?", (mid, user_id)) > 0


def clear(user_id: str) -> int:
    return db.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))


def search(user_id: str, q: str, limit: int = 5) -> list[dict]:
    """Busca textual simples com pontuação por termo (local, sem serviço externo)."""
    termos = [t for t in re.findall(r"\w{2,}", q.lower())]
    if not termos:
        return []
    mems = list_for(user_id)
    scored = []
    for m in mems:
        alvo = m["text"].lower()
        score = sum(alvo.count(t) for t in termos)
        if score:
            scored.append((score, m))
    scored.sort(key=lambda x: -x[0])
    return [m for _, m in scored[:limit]]


def export(user_id: str) -> list[dict]:
    return list_for(user_id)
