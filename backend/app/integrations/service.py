"""Autorização das integrações (permissões de fonte). Tokens nunca vão a log."""
from __future__ import annotations

import base64
import os
from datetime import datetime, timezone

from backend.app import config
from backend.app.integrations.catalog import CATALOGO
from backend.app.storage import db

_BY_ID = {c["id"]: c for c in CATALOGO}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key() -> bytes:
    path = config.DATA_DIR / "integrations.key"
    if not path.exists():
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(os.urandom(32))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path.read_bytes()


def _enc(text: str) -> str:
    key = _key()
    iv = os.urandom(16)
    raw = text.encode("utf-8")
    out = bytes(b ^ key[i % len(key)] ^ iv[i % 16] for i, b in enumerate(raw))
    return base64.b64encode(iv + out).decode("ascii")


def _dec(blob: str) -> str:
    raw = base64.b64decode(blob.encode("ascii"))
    iv, data = raw[:16], raw[16:]
    key = _key()
    return bytes(b ^ key[i % len(key)] ^ iv[i % 16] for i, b in enumerate(data)).decode("utf-8")


def listar(user_id: str) -> list[dict]:
    rows = {
        r["integration_id"]: r
        for r in db.query(
            "SELECT integration_id, authorized_at, has_token FROM integration_auth WHERE user_id = ?",
            (user_id,),
        )
    }
    out = []
    for c in CATALOGO:
        st = rows.get(c["id"])
        item = dict(c)
        item["authorized"] = st is not None
        item["authorized_at"] = st["authorized_at"] if st else None
        item["has_token"] = bool(st["has_token"]) if st else False
        item.pop("token", None)
        out.append(item)
    return out


def is_authorized(user_id: str, integration_id: str) -> bool:
    rows = db.query(
        "SELECT 1 FROM integration_auth WHERE user_id = ? AND integration_id = ?",
        (user_id, integration_id),
    )
    return bool(rows)


def authorize(user_id: str, integration_id: str, token: str | None = None) -> dict:
    if integration_id not in _BY_ID:
        raise KeyError(integration_id)
    token_blob = _enc(token.strip()) if token and token.strip() else None
    db.execute(
        "INSERT OR REPLACE INTO integration_auth (user_id, integration_id, authorized_at, token_enc, has_token) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, integration_id, _now(), token_blob, 1 if token_blob else 0),
    )
    return {"id": integration_id, "authorized": True, "has_token": bool(token_blob)}


def revoke(user_id: str, integration_id: str) -> None:
    db.execute(
        "DELETE FROM integration_auth WHERE user_id = ? AND integration_id = ?",
        (user_id, integration_id),
    )


def token_de(user_id: str, integration_id: str) -> str | None:
    rows = db.query(
        "SELECT token_enc FROM integration_auth WHERE user_id = ? AND integration_id = ?",
        (user_id, integration_id),
    )
    if not rows or not rows[0]["token_enc"]:
        return None
    try:
        return _dec(rows[0]["token_enc"])
    except Exception:
        return None
