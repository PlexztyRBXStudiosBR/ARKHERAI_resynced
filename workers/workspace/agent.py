#!/usr/bin/env python3
"""Agente ARKHER do PC virtual — stdlib only.

Inspirado no protótipo ArkherAI (agent.py / DsOS), SEM modelos de IA
de terceiros: nada de Puter, Shap-E, TripoSR, HF inferência no chat.
O chat da ARKHER é próprio; este processo só opera o *seu* PC.

  ARKHER_AGENT_TOKEN=agt_… python workers/workspace/agent.py

Rotas (todas exigem o token):
  GET  /health
  POST /autologon     AutoAdminLogon Windows (credenciais da VM do usuário)
  POST /job           trabalhos permitidos (não é shell aberto)
  GET  /screen
"""
from __future__ import annotations

import base64
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import urllib.request
from urllib.parse import urlparse

PORT = int(os.environ.get("ARKHER_AGENT_PORT", "8765"))
TOKEN = os.environ.get("ARKHER_AGENT_TOKEN", "")
STATE = Path(os.environ.get("ARKHER_STATE") or Path.home() / "arkher_state")
WORK = STATE / "work"
WORK.mkdir(parents=True, exist_ok=True)
IS_WIN = platform.system() == "Windows"
BOOT = time.time()

APPS = {
    "studio": [
        r"%LOCALAPPDATA%\Roblox\Versions",
        "RobloxStudioBeta.exe",
        "RobloxStudio.exe",
    ],
    "blender": ["blender", "Blender.exe"],
    "code": ["code", "Code.exe"],
}


def _auth(handler) -> bool:
    got = handler.headers.get("Authorization", "")
    if got.startswith("Bearer "):
        got = got[7:]
    got = got or handler.headers.get("X-Arkher-Agent", "")
    if not TOKEN:
        return False
    return got == TOKEN


def machine() -> dict:
    info = {
        "host": platform.node(),
        "sistema": platform.system(),
        "release": platform.release(),
        "python": platform.python_version(),
        "uptime_s": int(time.time() - BOOT),
        "cwd": str(WORK),
    }
    return info


def autologon(username: str, password: str) -> dict:
    if not IS_WIN:
        return {"ok": False, "message": "Auto-logon é Windows (registry AutoAdminLogon)."}
    # Não ecoa a senha. Script gerado localmente e executado.
    ps = r"""
$ErrorActionPreference='Stop'
$u = $env:ARKHER_AUTO_USER
$p = $env:ARKHER_AUTO_PASS
Set-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -Name AutoAdminLogon -Value '1'
Set-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -Name DefaultUserName -Value $u
Set-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -Name DefaultPassword -Value $p
Write-Output 'ARKHER_AUTOLOGON_OK'
"""
    env = os.environ.copy()
    env["ARKHER_AUTO_USER"] = username
    env["ARKHER_AUTO_PASS"] = password
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=30, env=env,
        )
        ok = r.returncode == 0 and "ARKHER_AUTOLOGON_OK" in (r.stdout or "")
        return {
            "ok": ok,
            "code": r.returncode,
            "out": (r.stdout or "")[-2000:],
            "err": (r.stderr or "")[-1000:],
        }
    except Exception as e:
        return {"ok": False, "message": f"{type(e).__name__}: {e}"}


def _which(names) -> str | None:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
        exp = os.path.expandvars(n)
        if os.path.isfile(exp):
            return exp
    return None


def screenshot() -> dict:
    if IS_WIN:
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            "$bmp = New-Object System.Drawing.Bitmap $b.Width,$b.Height; "
            "$g = [System.Drawing.Graphics]::FromImage($bmp); "
            "$g.CopyFromScreen($b.Location,[Drawing.Point]::Empty,$b.Size); "
            "$ms = New-Object IO.MemoryStream; "
            "$bmp.Save($ms,[Drawing.Imaging.ImageFormat]::Jpeg); "
            "[Convert]::ToBase64String($ms.ToArray())"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=20,
        )
        b64 = (r.stdout or "").strip()
        if r.returncode == 0 and b64:
            return {"ok": True, "mime": "image/jpeg", "b64": b64[: 2_000_000]}
        return {"ok": False, "message": (r.stderr or "falha no print")[-400:]}
    return {"ok": False, "message": "screenshot só implementado no Windows neste agente."}


def install_app(nome: str) -> dict:
    """Instala só Studio ou Blender — lista fechada, sem shell livre."""
    nome = (nome or "").lower().strip()
    if nome in ("studio", "roblox", "robloxstudio"):
        got = _which(["RobloxStudioBeta.exe", "RobloxStudio.exe"])
        if got:
            return {"ok": True, "app": "studio", "already": True, "exe": got}
        if not IS_WIN:
            return {"ok": False, "message": "Roblox Studio instala no Windows da VM."}
        setup = WORK / "RobloxStudioLauncherBeta.exe"
        if not setup.exists():
            try:
                urllib.request.urlretrieve(  # noqa: S310 — URL oficial da Roblox
                    "https://setup.rbxcdn.com/RobloxStudioLauncherBeta.exe",
                    setup,
                )
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "message": f"download Studio falhou: {e}"}
        subprocess.Popen([str(setup)], cwd=str(WORK))
        return {"ok": True, "app": "studio", "started_installer": True, "setup": str(setup)}
    if nome in ("blender",):
        got = _which(["blender", "Blender.exe"])
        if got:
            return {"ok": True, "app": "blender", "already": True, "exe": got}
        winget = shutil.which("winget")
        if IS_WIN and winget:
            r = subprocess.run(
                [winget, "install", "-e", "--id", "BlenderFoundation.Blender",
                 "--accept-package-agreements", "--accept-source-agreements"],
                capture_output=True, text=True, timeout=600,
            )
            return {
                "ok": r.returncode == 0,
                "app": "blender",
                "out": (r.stdout or r.stderr or "")[-1500:],
            }
        return {"ok": False, "message": "Blender: instale ou coloque no PATH. Sem winget neste PC."}
    return {"ok": False, "message": f"install não permitido: {nome}"}


def open_app(nome: str) -> dict:
    nome = (nome or "").lower()
    if nome in ("studio", "roblox", "robloxstudio"):
        exe = _which(["RobloxStudioBeta.exe", "RobloxStudio.exe"])
        if not exe:
            inst = install_app("studio")
            exe = _which(["RobloxStudioBeta.exe", "RobloxStudio.exe"])
            if not exe:
                return {"ok": False, "message": "Studio não estava instalado; iniciei o instalador oficial.", "install": inst}
        subprocess.Popen([exe], cwd=str(WORK))
        return {"ok": True, "app": "studio", "exe": exe}
    if nome in ("blender",):
        exe = _which(["blender", "Blender.exe"])
        if not exe:
            inst = install_app("blender")
            exe = _which(["blender", "Blender.exe"])
            if not exe:
                return {"ok": False, "message": "Blender não estava instalado; tentei o winget.", "install": inst}
        subprocess.Popen([exe], cwd=str(WORK))
        return {"ok": True, "app": "blender", "exe": exe}
    if nome in ("code", "vscode"):
        exe = _which(["code", "Code.exe"])
        if not exe:
            return {"ok": False, "message": "VS Code não encontrado."}
        subprocess.Popen([exe, str(WORK)])
        return {"ok": True, "app": "code"}
    return {"ok": False, "message": f"app não permitida: {nome}"}


def convert_rbx(src: str, dest: str | None = None) -> dict:
    src_p = Path(src)
    if not src_p.is_file():
        return {"ok": False, "message": "arquivo fonte inexistente"}
    tool = shutil.which("rbx-util") or shutil.which("rbx-dom")
    dest_p = Path(dest) if dest else WORK / (src_p.stem + (".rbxlx" if src_p.suffix.lower() == ".rbxl" else ".rbxmx"))
    if src_p.open("rb").read(80).lstrip().startswith(b"<"):
        if src_p.resolve() != dest_p.resolve():
            shutil.copy2(src_p, dest_p)
        return {"ok": True, "dest": str(dest_p), "modo": "xml_copy", "bytes": dest_p.stat().st_size}
    if not tool:
        return {"ok": False, "message": "rbx-util ausente; XML já existentes são copiados. Binário fica pendente."}
    r = subprocess.run([tool, "convert", str(src_p), str(dest_p)], capture_output=True, text=True, timeout=900)
    return {"ok": r.returncode == 0 and dest_p.exists(), "dest": str(dest_p), "out": (r.stdout or r.stderr or "")[-1000:]}


def import_place(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "message": "place não encontrado"}
    # Abre o XML no Studio (o Studio associa .rbxlx)
    if IS_WIN:
        os.startfile(str(p))  # noqa: S606 — arquivo local do usuário
        return {"ok": True, "opened": str(p)}
    subprocess.Popen(["xdg-open", str(p)])
    return {"ok": True, "opened": str(p)}


def blender_script(conteudo: str, nome: str = "arkher.py") -> dict:
    alvo = WORK / Path(nome).name
    alvo.write_text(conteudo, encoding="utf-8")
    exe = _which(["blender", "Blender.exe"])
    if not exe:
        return {"ok": True, "script": str(alvo), "ran": False, "message": "script salvo; Blender não está neste PC."}
    r = subprocess.run([exe, "--background", "--python", str(alvo)], capture_output=True, text=True, timeout=600)
    return {"ok": r.returncode == 0, "script": str(alvo), "ran": True, "out": (r.stdout or "")[-2000:]}


def sync_file(nome: str, conteudo: str, conteudo_b64: str = "") -> dict:
    alvo = WORK / Path(nome).name
    if conteudo_b64:
        alvo.write_bytes(base64.b64decode(conteudo_b64))
    else:
        alvo.write_text(conteudo, encoding="utf-8")
    return {"ok": True, "path": str(alvo), "bytes": alvo.stat().st_size}


def click(x: int, y: int) -> dict:
    x, y = int(x), int(y)
    if not (0 <= x <= 10000 and 0 <= y <= 10000):
        return {"ok": False, "message": "coordenada fora do limite"}
    if not IS_WIN:
        return {"ok": False, "message": "click só no Windows neste agente"}
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point {x},{y}; "
        "Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; "
        "public class M { [DllImport(\"user32.dll\")] public static extern void mouse_event(int d,int x,int y,int c,int e); }'; "
        "[M]::mouse_event(0x0002,0,0,0,0); [M]::mouse_event(0x0004,0,0,0,0)"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True, timeout=8)
    return {"ok": r.returncode == 0, "x": x, "y": y, "err": (r.stderr or "")[-300:]}


def type_text(text: str) -> dict:
    text = (text or "")[:200]
    if not text:
        return {"ok": False, "message": "texto vazio"}
    if not IS_WIN:
        return {"ok": False, "message": "digitar só no Windows neste agente"}
    # SendKeys: escapa só o necessário, sem comandos de sistema.
    safe = text.replace("{", "{{").replace("}", "}}")
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.SendKeys]::SendWait('{safe.replace(chr(39), chr(39)+chr(39))}')"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True, timeout=8)
    return {"ok": r.returncode == 0, "n": len(text)}


def ls(path: str | None = None) -> dict:
    p = Path(path) if path else WORK
    if not p.exists():
        return {"ok": False, "message": "path inexistente"}
    itens = []
    for c in sorted(p.iterdir())[:200]:
        itens.append({"nome": c.name, "dir": c.is_dir(), "bytes": c.stat().st_size if c.is_file() else 0})
    return {"ok": True, "path": str(p), "itens": itens}


def run_job(kind: str, args: dict) -> dict:
    if kind == "screenshot":
        return screenshot()
    if kind == "install_app":
        return install_app(str(args.get("app", "")))
    if kind == "open_app":
        return open_app(str(args.get("app", "")))
    if kind == "convert_rbx":
        return convert_rbx(str(args.get("src", "")), args.get("dest"))
    if kind == "import_place":
        return import_place(str(args.get("path", "")))
    if kind == "blender_script":
        return blender_script(str(args.get("conteudo", "")), str(args.get("nome", "arkher.py")))
    if kind == "sync_file":
        return sync_file(
            str(args.get("nome", "arquivo.txt")),
            str(args.get("conteudo", "")),
            str(args.get("conteudo_b64", "") or ""),
        )
    if kind == "click":
        return click(int(args.get("x", 0) or 0), int(args.get("y", 0) or 0))
    if kind == "type":
        return type_text(str(args.get("text", "")))
    if kind == "ls":
        return ls(args.get("path"))
    if kind in ("health", "status"):
        return {"ok": True, **machine()}
    return {"ok": False, "message": f"job desconhecido: {kind}"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[arkher-agent] " + (fmt % args) + "\n")

    def _json(self, code: int, payload: dict):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_GET(self):
        if not _auth(self):
            return self._json(401, {"ok": False, "code": "UNAUTHORIZED"})
        path = urlparse(self.path).path
        if path == "/health":
            return self._json(200, {"ok": True, **machine()})
        if path == "/screen":
            return self._json(200, screenshot())
        return self._json(404, {"ok": False, "code": "NOT_FOUND"})

    def do_POST(self):
        if not _auth(self):
            return self._json(401, {"ok": False, "code": "UNAUTHORIZED"})
        path = urlparse(self.path).path
        body = self._body()
        if path == "/autologon":
            return self._json(200, autologon(str(body.get("username", "")), str(body.get("password", ""))))
        if path == "/job":
            return self._json(200, run_job(str(body.get("kind", "")), body.get("args") or {}))
        return self._json(404, {"ok": False, "code": "NOT_FOUND"})


def main() -> int:
    if not TOKEN:
        print("defina ARKHER_AGENT_TOKEN", file=sys.stderr)
        return 2
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"ARKHER agent {PORT} host={platform.node()}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
