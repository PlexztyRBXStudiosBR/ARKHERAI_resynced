"""Workspace: PCs virtuais do usuário (Tailscale + agente ARKHER).

O usuário cola o IP Tailscale e a senha da VM. O backend NÃO abre shell
arbitrário na internet pública: só fala com IPs da malha (Tailscale/LAN)
no agente próprio (porta 8765), com token. Auto-logon é um script Windows
que o agente aplica na *máquina do usuário*, com a permissão dele.
"""
from __future__ import annotations

import base64
import ipaddress
import json
import os
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timezone

from backend.app import config
from backend.app.storage import db

AGENT_PORT = int(os.environ.get("ARKHER_AGENT_PORT", "8765"))
HEALTH_TIMEOUT = 4.0
JOB_TIMEOUT = 30.0
JOB_TIMEOUTS = {
    "install_app": 600.0,
    "convert_rbx": 900.0,
    "import_place": 60.0,
    "blender_script": 600.0,
    "screenshot": 20.0,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key() -> bytes:
    path = config.DATA_DIR / "workspace.key"
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


def ip_permitido(ip: str) -> bool:
    """Bloqueia SSRF: só Tailscale CGNAT, loopback e RFC1918."""
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        return False
    if addr.version != 4:
        return False
    if addr.is_link_local or addr.is_multicast or addr.is_reserved or addr.is_unspecified:
        return False
    if addr in ipaddress.ip_network("100.64.0.0/10"):
        return True
    if addr.is_loopback or addr.is_private:
        return True
    return False


class WorkspaceError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def listar(user_id: str) -> list[dict]:
    rows = db.query(
        "SELECT id, name, tailscale_ip, username, status, last_seen, created_at FROM vms "
        "WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    return [dict(r) for r in rows]


def obter(user_id: str, vm_id: str) -> dict | None:
    rows = db.query(
        "SELECT id, name, tailscale_ip, username, status, last_seen, created_at, agent_token_hash "
        "FROM vms WHERE id = ? AND user_id = ?",
        (vm_id, user_id),
    )
    return dict(rows[0]) if rows else None


def criar(user_id: str, name: str, tailscale_ip: str, username: str, password: str) -> dict:
    ip = tailscale_ip.strip()
    if not ip_permitido(ip):
        raise WorkspaceError(
            "BAD_IP",
            "Use um IP Tailscale (100.x) ou da sua LAN. IPs públicos são recusados (SSRF).",
        )
    if not username.strip() or len(username) > 80:
        raise WorkspaceError("BAD_USER", "Usuário da VM inválido.")
    if not password or len(password) > 200:
        raise WorkspaceError("BAD_PASSWORD", "Senha da VM inválida.")
    vid = "vm_" + secrets.token_hex(6)
    agent_token = "agt_" + secrets.token_hex(16)
    db.execute(
        "INSERT INTO vms (id, user_id, name, tailscale_ip, username, password_enc, agent_token_enc, "
        "agent_token_hash, status, last_seen, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            vid,
            user_id,
            (name or "PC virtual").strip()[:60],
            ip,
            username.strip()[:80],
            _enc(password),
            _enc(agent_token),
            agent_token[:12] + "…",
            "offline",
            None,
            _now(),
        ),
    )
    vm = obter(user_id, vid)
    assert vm is not None
    vm["agent_token"] = agent_token  # mostrado UMA vez na criação
    return vm


def apagar(user_id: str, vm_id: str) -> bool:
    return db.execute("DELETE FROM vms WHERE id = ? AND user_id = ?", (vm_id, user_id)) > 0


def _segredos(user_id: str, vm_id: str) -> tuple[str, str, str]:
    rows = db.query(
        "SELECT tailscale_ip, password_enc, agent_token_enc FROM vms WHERE id = ? AND user_id = ?",
        (vm_id, user_id),
    )
    if not rows:
        raise WorkspaceError("NOT_FOUND", "PC virtual não encontrado.")
    r = rows[0]
    return r["tailscale_ip"], _dec(r["password_enc"]), _dec(r["agent_token_enc"])


def _agent(ip: str, token: str, method: str, path: str, body: dict | None = None, timeout: float = HEALTH_TIMEOUT) -> dict:
    if not ip_permitido(ip):
        raise WorkspaceError("BAD_IP", "IP não permitido.")
    url = f"http://{ip}:{AGENT_PORT}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Arkher-Agent", token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise WorkspaceError("AGENT_HTTP", f"Agente respondeu HTTP {e.code}.") from e
    except urllib.error.URLError as e:
        raise WorkspaceError("AGENT_OFFLINE", f"Agente inacessível em {ip}:{AGENT_PORT} — {e.reason}.") from e
    except TimeoutError as e:
        raise WorkspaceError("AGENT_TIMEOUT", "O agente não respondeu a tempo.") from e


def health(user_id: str, vm_id: str) -> dict:
    ip, _pw, token = _segredos(user_id, vm_id)
    try:
        info = _agent(ip, token, "GET", "/health")
        db.execute(
            "UPDATE vms SET status = ?, last_seen = ? WHERE id = ? AND user_id = ?",
            ("online", _now(), vm_id, user_id),
        )
        return {"ok": True, "status": "online", "agente": info}
    except WorkspaceError as e:
        db.execute(
            "UPDATE vms SET status = ? WHERE id = ? AND user_id = ?",
            ("offline", vm_id, user_id),
        )
        return {"ok": False, "status": "offline", "code": e.code, "message": e.message}


def autologon(user_id: str, vm_id: str) -> dict:
    """Pede ao agente para aplicar AutoAdminLogon com as credenciais da VM."""
    ip, password, token = _segredos(user_id, vm_id)
    vm = obter(user_id, vm_id)
    if vm is None:
        raise WorkspaceError("NOT_FOUND", "PC virtual não encontrado.")
    return _agent(
        ip,
        token,
        "POST",
        "/autologon",
        {"username": vm["username"], "password": password},
        timeout=JOB_TIMEOUT,
    )


def job(user_id: str, vm_id: str, kind: str, args: dict) -> dict:
    permitidos = {
        "health",
        "screenshot",
        "open_app",
        "convert_rbx",
        "import_place",
        "blender_script",
        "sync_file",
        "ls",
        "status",
        "click",
        "type",
        "install_app",
    }
    if kind not in permitidos:
        raise WorkspaceError("BAD_JOB", f"Trabalho não permitido: {kind}")
    ip, _pw, token = _segredos(user_id, vm_id)
    timeout = JOB_TIMEOUTS.get(kind, JOB_TIMEOUT)
    return _agent(ip, token, "POST", "/job", {"kind": kind, "args": args or {}}, timeout=timeout)


def token_agente(user_id: str, vm_id: str) -> str:
    _ip, _pw, token = _segredos(user_id, vm_id)
    return token


def screen(user_id: str, vm_id: str) -> dict:
    ip, _pw, token = _segredos(user_id, vm_id)
    shot = _agent(ip, token, "GET", "/screen", timeout=8.0)
    db.execute(
        "UPDATE vms SET status = ?, last_seen = ? WHERE id = ? AND user_id = ?",
        ("online", _now(), vm_id, user_id),
    )
    return shot
