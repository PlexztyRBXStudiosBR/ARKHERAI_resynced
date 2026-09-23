"""Autenticação própria em modo local: identidade de dispositivo + token bearer.

Sem provedor externo de identidade. Tokens são armazenados apenas como hash.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Query

from backend.app.storage import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register_device(name: str) -> dict:
    user_id = "u_" + secrets.token_hex(8)
    token = "ark_" + secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO users (id, name, token_hash, created_at) VALUES (?, ?, ?, ?)",
        (user_id, name.strip()[:60] or "usuário", _hash(token), _now()),
    )
    return {"token": token, "user": {"id": user_id, "name": name.strip()[:60] or "usuário"}}


def user_by_token(token: str) -> dict | None:
    rows = db.query("SELECT id, name FROM users WHERE token_hash = ?", (_hash(token),))
    if not rows:
        return None
    return {"id": rows[0]["id"], "name": rows[0]["name"]}


def require_user(
    authorization: str | None = Header(default=None),
    x_arkher_token: str | None = Header(default=None),
) -> dict:
    """Aceita `Authorization: Bearer …` ou o cabeçalho próprio `X-Arkher-Token`.

    O cabeçalho próprio existe porque alguns proxies descartam `Authorization`;
    o token é o mesmo e continua válido somente para o modo local.
    """
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_arkher_token:
        token = x_arkher_token.strip()
    if not token:
        raise HTTPException(status_code=401, detail={"ok": False, "code": "UNAUTHORIZED", "message": "Token ausente."})
    user = user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail={"ok": False, "code": "UNAUTHORIZED", "message": "Token inválido."})
    return user


CurrentUser = Depends(require_user)
