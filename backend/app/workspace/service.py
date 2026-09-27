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
from backend.app.workspace.usuario import estado_dir, usuario_sessao

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
    _gravar_token_agente(agent_token)
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


def _req(ip: str, token: str, method: str, path: str, body: dict | None = None, timeout: float = HEALTH_TIMEOUT):
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
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise WorkspaceError("AGENT_HTTP", f"Agente respondeu HTTP {e.code}.") from e
    except urllib.error.URLError as e:
        raise WorkspaceError("AGENT_OFFLINE", f"Agente inacessível em {ip}:{AGENT_PORT} — {e.reason}.") from e
    except TimeoutError as e:
        raise WorkspaceError("AGENT_TIMEOUT", "O agente não respondeu a tempo.") from e


def _agent(ip: str, token: str, method: str, path: str, body: dict | None = None, timeout: float = HEALTH_TIMEOUT) -> dict:
    try:
        with _req(ip, token, method, path, body, timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise WorkspaceError("AGENT_HTTP", "Agente não devolveu JSON.") from e


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


def _token_paths() -> list:
    from pathlib import Path

    return [
        estado_dir() / "agent.token",
        Path(r"C:\Users\nexus") / "arkher_state" / "agent.token",
        Path.home() / "arkher_state" / "agent.token",
        config.DATA_DIR / "agent.token",
    ]


def _gravar_token_agente(token: str) -> None:
    from pathlib import Path

    for p in _token_paths():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(token, encoding="utf-8")
            try:
                p.chmod(0o600)
            except OSError:
                pass
        except OSError:
            continue


def tailscale_ip_local() -> str:
    exe = shutil_which_ts()
    if not exe:
        return ""
    try:
        r = subprocess_run_ts(exe)
        return (r or "").strip().splitlines()[0] if r else ""
    except Exception:
        return ""


def shutil_which_ts() -> str:
    import shutil
    from pathlib import Path

    w = shutil.which("tailscale")
    if w:
        return w
    win = Path(r"C:\Program Files\Tailscale\tailscale.exe")
    return str(win) if win.exists() else ""


def subprocess_run_ts(exe: str) -> str:
    import subprocess

    r = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True, timeout=15)
    return r.stdout or ""


def ponte() -> dict:
    """O que este PC oferece: Tailscale, agente local, URL HTTPS se Serve estiver ligado."""
    ts = tailscale_ip_local()
    agent_ok = False
    try:
        raw = _agent(ts or "127.0.0.1", _ler_token() or "x", "GET", "/health", timeout=2.0)
        agent_ok = bool(raw.get("ok"))
    except WorkspaceError:
        try:
            raw = _agent("127.0.0.1", _ler_token() or "x", "GET", "/health", timeout=2.0)
            agent_ok = bool(raw.get("ok"))
        except WorkspaceError:
            agent_ok = False
    return {
        "ok": True,
        "tailscale_ip": ts,
        "agente_local": agent_ok,
        "backend": f"http://{ts}:8710" if ts else "",
        "nota": (
            "No celular use o site da Vercel + Config backend = https://SEU-PC.ts.net "
            "(Tailscale Serve). HTTPS da Vercel não fala com http://100.x."
            if ts
            else "Tailscale não respondeu neste PC."
        ),
    }


def _ler_token() -> str:
    for p in _token_paths():
        try:
            t = p.read_text(encoding="utf-8").strip()
            if t.startswith("agt_"):
                return t
        except OSError:
            continue
    return os.environ.get("ARKHER_AGENT_TOKEN", "")


def auto_este_pc(user_id: str, username: str = "", password: str = "") -> dict:
    """Cadastra ESTE Windows (onde o uvicorn roda) como VM 127.0.0.1."""
    ts = tailscale_ip_local()
    existentes = listar(user_id)
    for vm in existentes:
        if vm.get("tailscale_ip") in ("127.0.0.1", ts):
            h = health(user_id, vm["id"])
            return {"ok": True, "vm": vm, "health": h, "reuso": True}
    vm = criar(
        user_id,
        "Este PC",
        "127.0.0.1",
        (username or usuario_sessao())[:80],
        password or "local",
    )
    h = health(user_id, vm["id"])
    return {"ok": True, "vm": vm, "health": h, "reuso": False, "tailscale_ip": ts}


def detect_github(user_id: str, repo: str = "") -> dict:
    """Lê o run MAIS NOVO do Actions (não dispara workflow). Pega TAILSCALE_IP do log."""
    from backend.app.integrations import service as integ

    pat = integ.token_de(user_id, "github")
    if not pat:
        raise WorkspaceError("NO_GITHUB", "Autorize GitHub em Integrações e cole um PAT (Actions: read).")
    repo = (repo or os.environ.get("ARKHER_VM_REPO") or "PlexztyRBXStudiosBR/ArkherAI").strip()
    api = "https://api.github.com"
    headers = {
        "Authorization": "Bearer " + pat,
        "Accept": "application/vnd.github+json",
        "User-Agent": "ARKHER",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    def gh(path: str) -> tuple[bytes, str]:
        req = urllib.request.Request(api + path, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read(), resp.headers.get("Content-Type") or ""
        except urllib.error.HTTPError as e:
            raise WorkspaceError("GITHUB", f"GitHub HTTP {e.code} em {path}") from e

    raw, _ = gh(f"/repos/{repo}/actions/runs?per_page=8")
    runs = (json.loads(raw.decode("utf-8", "replace")) or {}).get("workflow_runs") or []
    if not runs:
        raise WorkspaceError("NO_RUN", f"Nenhum run em {repo}. Ligue a VM no Actions (manual, não 24h).")
    run = runs[0]
    logs, _ct = gh(f"/repos/{repo}/actions/runs/{run['id']}/logs")
    texto = _unzip_text(logs)
    achado = _parse_rdp_log(texto)
    if not achado.get("ip"):
        raise WorkspaceError(
            "NO_IP",
            "Run existe mas o log não tem TAILSCALE_IP. A VM ainda está subindo, ou o workflow não imprime o IP.",
        )
    for vm0 in listar(user_id):
        if vm0.get("tailscale_ip") == achado["ip"]:
            return {"ok": True, "vm": vm0, "run": run.get("html_url"), "ip": achado["ip"], "reuso": True,
                    "aviso": "Não disparamos o workflow. Só lemos o que já estava no ar."}
    vm = criar(
        user_id,
        f"VM {repo.split('/')[-1]}",
        achado["ip"],
        usuario_sessao(),
        achado.get("senha") or "vm",
    )
    return {
        "ok": True,
        "vm": {k: vm[k] for k in vm if k != "agent_token"} | {"agent_token": vm.get("agent_token")},
        "run": run.get("html_url"),
        "ip": achado["ip"],
        "aviso": "Não disparamos o workflow. Só lemos o que já estava no ar.",
    }


def _unzip_text(blob: bytes) -> str:
    import io
    import zipfile

    if blob[:2] != b"PK":
        return blob.decode("utf-8", "replace")
    parts = []
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for n in z.namelist()[:40]:
            try:
                parts.append(z.read(n).decode("utf-8", "replace"))
            except Exception:
                continue
    return "\n".join(parts)


def _parse_rdp_log(texto: str) -> dict:
    import re

    t = re.sub(r"\x1b\[[0-9;]*m", "", texto or "")
    def acha(rx: str) -> str:
        m = re.search(rx, t, re.I)
        return m.group(1).strip() if m else ""
    ip = (
        acha(r"TAILSCALE_IP=((?:\d{1,3}\.){3}\d{1,3})")
        or acha(r"Address:\s*((?:\d{1,3}\.){3}\d{1,3})")
        or acha(r"\b(100\.(?:\d{1,3}\.){2}\d{1,3})\b")
    )
    usuario = acha(r"Username:\s*(\S+)") or acha(r"usuario:\s*(\S+)") or acha(r"User:\s*(\S+)")
    senha = acha(r"Password:\s*(\S+)") or acha(r"senha:\s*(\S+)")
    if senha in ("***",):
        senha = ""
    return {"ip": ip, "usuario": usuario, "senha": senha}


def token_agente(user_id: str, vm_id: str) -> str:
    _ip, _pw, token = _segredos(user_id, vm_id)
    return token


def _frame_b64(shot: dict) -> str:
    """O agente antigo manda só `img` (data URL). O nosso manda `b64` e `img`."""
    if not isinstance(shot, dict):
        return ""
    for k in ("b64", "img", "jpeg", "jpg", "png", "image", "image_b64", "data"):
        v = shot.get(k)
        if isinstance(v, str) and len(v) > 80:
            if v.startswith("data:"):
                v = v.split(",", 1)[-1]
            return "".join(v.split())
    inner = shot.get("result") or shot.get("screen") or {}
    if isinstance(inner, dict):
        return _frame_b64(inner)
    return ""


def screen(user_id: str, vm_id: str, scale: float = 0.45, quality: int = 50) -> dict:
    ip, _pw, token = _segredos(user_id, vm_id)
    scale = max(0.15, min(1.0, float(scale or 0.45)))
    quality = max(20, min(90, int(quality or 50)))
    qs = f"/screen?scale={scale}&q={quality}"
    try:
        shot = _agent(ip, token, "GET", qs, timeout=14.0)
    except WorkspaceError:
        try:
            shot = _agent(ip, token, "POST", "/job", {"kind": "screenshot", "args": {}}, timeout=14.0)
        except WorkspaceError as e:
            return {"ok": False, "b64": "", "message": e.message}
    db.execute(
        "UPDATE vms SET status = ?, last_seen = ? WHERE id = ? AND user_id = ?",
        ("online", _now(), vm_id, user_id),
    )
    b64 = _frame_b64(shot if isinstance(shot, dict) else {})
    if b64:
        return {
            "ok": True,
            "b64": b64,
            "mime": "image/jpeg",
            "w": shot.get("w") if isinstance(shot, dict) else 0,
            "h": shot.get("h") if isinstance(shot, dict) else 0,
            "real_w": shot.get("real_w") if isinstance(shot, dict) else 0,
            "real_h": shot.get("real_h") if isinstance(shot, dict) else 0,
            "titulo": (shot.get("titulo") if isinstance(shot, dict) else "") or "",
        }
    msg = ""
    if isinstance(shot, dict):
        msg = str(shot.get("message") or shot.get("error") or shot.get("err") or "")
    if not msg:
        msg = (
            "sem frame: o agente está online mas não capturou a tela. "
            "Rode o agent.py DESTE repo DENTRO da sessão do Windows App (tela desbloqueada)."
        )
    return {"ok": False, "b64": "", "message": msg}


def frame_jpeg(user_id: str, vm_id: str, scale: float = 0.45, quality: int = 50) -> tuple[bytes, dict]:
    """JPEG cru (DsOS /frame). Se o agente antigo não tiver /frame, cai no /screen JSON."""
    ip, _pw, token = _segredos(user_id, vm_id)
    scale = max(0.15, min(1.0, float(scale or 0.45)))
    quality = max(20, min(90, int(quality or 50)))
    try:
        with _req(ip, token, "GET", f"/frame?scale={scale}&q={quality}", timeout=14.0) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            raw = resp.read()
            if "jpeg" in ctype or (raw[:2] == b"\xff\xd8"):
                meta = {
                    "w": resp.headers.get("X-Arkher-W"),
                    "h": resp.headers.get("X-Arkher-H"),
                    "real_w": resp.headers.get("X-Arkher-Real-W"),
                    "real_h": resp.headers.get("X-Arkher-Real-H"),
                    "titulo": resp.headers.get("X-Arkher-Title") or "",
                }
                db.execute(
                    "UPDATE vms SET status = ?, last_seen = ? WHERE id = ? AND user_id = ?",
                    ("online", _now(), vm_id, user_id),
                )
                return raw, meta
    except WorkspaceError:
        pass
    shot = screen(user_id, vm_id, scale, quality)
    if not shot.get("b64"):
        raise WorkspaceError("NO_FRAME", shot.get("message") or "sem frame")
    return base64.b64decode(shot["b64"]), shot


def input_acts(user_id: str, vm_id: str, acts: list) -> dict:
    ip, _pw, token = _segredos(user_id, vm_id)
    body = {"acts": [a for a in (acts or []) if isinstance(a, dict)][:40]}
    try:
        return _agent(ip, token, "POST", "/input", body, timeout=20.0)
    except WorkspaceError:
        # agente nosso antigo: job click/type um a um
        out = []
        for a in body["acts"][:8]:
            d = (a.get("do") or a.get("t") or "").lower()
            if d in ("click", "dblclick", "right"):
                out.append(job(user_id, vm_id, "click", {"x": a.get("x", 0), "y": a.get("y", 0)}))
            elif d in ("type", "text"):
                out.append(job(user_id, vm_id, "type", {"text": a.get("text") or a.get("txt") or ""}))
            else:
                out.append({"ok": False, "err": "agente sem /input para " + d})
        return {"ok": all(x.get("ok") for x in out) if out else False, "res": out}


def guiready(user_id: str, vm_id: str) -> dict:
    ip, _pw, token = _segredos(user_id, vm_id)
    try:
        return _agent(ip, token, "GET", "/guiready", timeout=10.0)
    except WorkspaceError as e:
        return {"ok": False, "nota": e.message}
