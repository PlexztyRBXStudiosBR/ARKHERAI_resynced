"""Feedback do usuário sobre respostas — sinal de aprendizado vindo do uso real.

Não raspamos nada de fora: quando o usuário marca uma resposta como boa ou ruim,
isso vira um registro estruturado que pode orientar os próximos ciclos de treino.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from backend.app.storage import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add(user_id: str, session_id: str, rating: int, note: str, content_hash: str) -> dict:
    if rating not in (-1, 1):
        raise ValueError("rating deve ser 1 ou -1")
    db.execute(
        "INSERT INTO feedback (user_id, session_id, content_hash, rating, note, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, session_id or "", re.sub(r"[^a-f0-9]", "", content_hash)[:64], rating, (note or "").strip()[:400], _now()),
    )
    return {"rating": rating}


def stats(user_id: str) -> dict:
    rows = db.query(
        "SELECT COALESCE(SUM(rating=1),0) AS bons, COALESCE(SUM(rating=-1),0) AS ruins, COUNT(*) AS total "
        "FROM feedback WHERE user_id = ?",
        (user_id,),
    )
    r = rows[0]
    return {"bons": r["bons"], "ruins": r["ruins"], "total": r["total"]}


def export(user_id: str) -> list[dict]:
    rows = db.query(
        "SELECT session_id, content_hash, rating, note, created_at FROM feedback "
        "WHERE user_id = ? ORDER BY id DESC LIMIT 1000",
        (user_id,),
    )
    return [dict(r) for r in rows]


def hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
