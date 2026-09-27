#!/usr/bin/env python3
"""Agente ARKHER — olhos e mãos do PC virtual (Windows App / Tailscale).

Protocolo do protótipo ArkherAI (agent.py + DsOS): /health /screen /frame
/guiready /input /app. SEM /infer, SEM Shap-E, SEM /exec aberto, SEM modelo
de terceiro. Um processo só (8765) pra não haver dois prints travando.

  ARKHER_AGENT_TOKEN=agt_… python agent.py
"""
from __future__ import annotations

import base64
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("ARKHER_AGENT_PORT") or os.environ.get("DSOS_PORT") or "8765")


def agent_token() -> str:
    t = (os.environ.get("ARKHER_AGENT_TOKEN") or "").strip()
    if t:
        return t
    for p in (STATE / "agent.token", Path.home() / "arkher_state" / "agent.token"):
        try:
            v = p.read_text(encoding="utf-8").strip()
            if v:
                return v
        except OSError:
            continue
    return ""
STATE = Path(os.environ.get("ARKHER_STATE") or Path.home() / "arkher_state")
WORK = STATE / "work"
WORK.mkdir(parents=True, exist_ok=True)
IS_WIN = platform.system() == "Windows"
BOOT = time.time()
PWSH = shutil.which("powershell") or shutil.which("pwsh") or "powershell"
_GRAB_LOCK = threading.Lock()
_LAST_JPEG = {"raw": b"", "meta": {}}

PS_GUI = r"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
Add-Type @'
using System;using System.Runtime.InteropServices;
public class M {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,int e);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h,System.Text.StringBuilder s,int n);
  public struct POINT { public int X; public int Y; }
  public static string Title(){ IntPtr h=GetForegroundWindow(); int n=GetWindowTextLength(h);
    var sb=new System.Text.StringBuilder(n+1); GetWindowText(h,sb,sb.Capacity); return sb.ToString(); }
  public static string Cursor(){ POINT p; GetCursorPos(out p); return p.X+"|"+p.Y; }
}
'@
"""


def _auth(handler) -> bool:
    tok = agent_token()
    got = handler.headers.get("Authorization", "")
    if got.startswith("Bearer "):
        got = got[7:]
    got = got or handler.headers.get("X-Arkher-Agent", "")
    q = parse_qs(urlparse(handler.path).query)
    got = got or (q.get("token") or [""])[0]
    if not tok:
        return False
    return got == tok


def ps(script: str, timeout: int = 60) -> tuple[str, str]:
    p = subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-STA", "-Command", script],
        capture_output=True,
        timeout=timeout,
    )
    return p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def ps_str(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def sendkeys_escape(txt: str) -> str:
    out = []
    for ch in str(txt):
        if ch in "+^%~(){}[]":
            out.append("{" + ch + "}")
        elif ch == "\n":
            out.append("{ENTER}")
        elif ch == "\t":
            out.append("{TAB}")
        else:
            out.append(ch)
    return "".join(out)


def grab_screen(scale: float = 0.5, quality: int = 55) -> dict:
    """JPEG da tela — mesmo método do ArkherAI (STA + VirtualScreen + arquivo)."""
    scale = max(0.15, min(1.0, float(scale)))
    quality = max(20, min(90, int(quality)))
    if not _GRAB_LOCK.acquire(blocking=False):
        if _LAST_JPEG["raw"]:
            meta = dict(_LAST_JPEG["meta"])
            meta["b64"] = base64.b64encode(_LAST_JPEG["raw"]).decode()
            meta["skipped"] = True
            return meta
        return {"err": "captura ocupada"}
    try:
        return _grab_screen_locked(scale, quality)
    finally:
        _GRAB_LOCK.release()


def _grab_screen_locked(scale: float, quality: int) -> dict:
    if not IS_WIN:
        disp = os.environ.get("DISPLAY") or os.environ.get("DSOS_DISPLAY") or ":0"
        out = STATE / "shot.jpg"
        try:
            if shutil.which("import"):
                subprocess.run(
                    ["import", "-display", disp, "-window", "root", "-quality", str(quality), str(out)],
                    timeout=20,
                    check=False,
                )
            elif shutil.which("ffmpeg"):
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "quiet", "-f", "x11grab", "-i", disp, "-frames:v", "1", "-q:v", "6", str(out)],
                    timeout=20,
                    check=False,
                )
            else:
                return {"err": "sem ferramenta de captura (sem sessão gráfica / sem import|ffmpeg)"}
            if not out.exists() or out.stat().st_size < 80:
                return {"err": "captura falhou (sem sessão gráfica em " + disp + "?)"}
            raw = out.read_bytes()
            _LAST_JPEG["raw"] = raw
            meta = {"b64": base64.b64encode(raw).decode(), "w": 0, "h": 0, "real_w": 0, "real_h": 0, "titulo": ""}
            _LAST_JPEG["meta"] = {k: meta[k] for k in ("w", "h", "real_w", "real_h", "titulo")}
            return meta
        except Exception as e:  # noqa: BLE001
            return {"err": str(e)}
    f = str(STATE / "shot.jpg").replace("'", "''")
    script = PS_GUI + f"""
$b=[System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height
$g=[System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.X,$b.Y,0,0,$bmp.Size)
$w=[int]($b.Width*{scale}); $h=[int]($b.Height*{scale})
if({scale} -ne 1.0){{ $r=New-Object System.Drawing.Bitmap $bmp,$w,$h; $bmp.Dispose(); $bmp=$r }}
$cod=[System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders()|?{{$_.MimeType -eq 'image/jpeg'}}
$pr=New-Object System.Drawing.Imaging.EncoderParameters 1
$pr.Param[0]=New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality),{quality}
$bmp.Save('{f}',$cod,$pr); $bmp.Dispose()
Write-Output "$w|$h|$($b.Width)|$($b.Height)|$([M]::Title())"
"""
    err = ""
    try:
        out, err = ps(script, 25)
        parts = (out.strip().splitlines() or [""])[-1].split("|")
        raw = (STATE / "shot.jpg").read_bytes()
        if len(raw) < 80:
            return {"err": "print vazio. Abra o Windows App, desbloqueie, rode este agente NA sessão. " + err[:200]}
        meta = {
            "b64": base64.b64encode(raw).decode(),
            "w": int(parts[0]) if len(parts) > 1 else 0,
            "h": int(parts[1]) if len(parts) > 1 else 0,
            "real_w": int(parts[2]) if len(parts) > 3 else 0,
            "real_h": int(parts[3]) if len(parts) > 3 else 0,
            "titulo": parts[4] if len(parts) > 4 else "",
        }
        _LAST_JPEG["raw"] = raw
        _LAST_JPEG["meta"] = {k: meta[k] for k in ("w", "h", "real_w", "real_h", "titulo")}
        return meta
    except Exception as e:  # noqa: BLE001
        return {"err": f"{e} :: {err[:300]}"}


def screen_payload(scale: float = 0.5, quality: int = 55) -> dict:
    g = grab_screen(scale, quality)
    if g.get("err"):
        return {"ok": False, "err": g["err"], "message": g["err"]}
    b64 = g["b64"]
    return {
        "ok": True,
        "b64": b64,
        "img": "data:image/jpeg;base64," + b64,
        "mime": "image/jpeg",
        "w": g.get("w") or 0,
        "h": g.get("h") or 0,
        "real_w": g.get("real_w") or 0,
        "real_h": g.get("real_h") or 0,
        "titulo": g.get("titulo") or "",
    }


def gui_ready() -> dict:
    if not IS_WIN:
        disp = os.environ.get("DISPLAY") or os.environ.get("DSOS_DISPLAY") or ":0"
        tem = os.path.exists("/tmp/.X11-unix/X" + disp.lstrip(":"))
        return {
            "ok": tem,
            "display": disp,
            "nota": None if tem else "sem servidor X em " + disp,
        }
    try:
        out, _ = ps("(quser) 2>&1 | Out-String", 20)
        ativo = "Active" in out or "Ativo" in out
        if not ativo:
            g = grab_screen(0.2, 30)
            ativo = bool(g.get("b64")) and (g.get("real_w") or 0) > 0
        return {
            "ok": ativo,
            "sessoes": out.strip()[:500],
            "nota": None if ativo else (
                "SEM SESSÃO GRÁFICA — entre pelo Windows App e rode este agente "
                "dentro dessa sessão (não lock screen)."
            ),
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "err": str(e), "nota": str(e)}


def do_input(act: dict) -> dict:
    d = (act.get("do") or act.get("t") or "").lower().strip()
    try:
        x, y = int(float(act.get("x", 0) or 0)), int(float(act.get("y", 0) or 0))
    except Exception:
        x, y = 0, 0
    if d in ("wait",):
        time.sleep(max(0.0, min(float(act.get("sec", 1) or 1), 8)))
        return {"ok": True}
    if d in ("app", "abrir"):
        return abrir_app(str(act.get("nome") or act.get("app") or ""), act.get("caminho"))
    if d in ("trackpad",):
        try:
            dx, dy = int(float(act.get("dx", 0) or 0)), int(float(act.get("dy", 0) or 0))
        except Exception:
            dx, dy = 0, 0
        if not IS_WIN:
            return {"ok": False, "err": "trackpad só no Windows neste agente"}
        S = PS_GUI + f"$c=[M]::Cursor() -split '\\|'; [M]::SetCursorPos(([int]$c[0])+({dx}),([int]$c[1])+({dy}))"
        try:
            out, err = ps(S, 8)
            return {"ok": not err.strip(), "err": err.strip()[:200] or None}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "err": str(e)}
    if not IS_WIN:
        if not shutil.which("xdotool"):
            return {"ok": False, "err": "sem xdotool"}
        env = dict(os.environ)
        env.setdefault("DISPLAY", os.environ.get("DSOS_DISPLAY", ":0"))

        def xd(*a):
            p = subprocess.run(["xdotool", *a], env=env, capture_output=True, text=True, timeout=15)
            return {"ok": p.returncode == 0, "err": (p.stderr or "")[:200] or None}

        if d == "move":
            return xd("mousemove", str(x), str(y))
        if d in ("click", "down"):
            return xd("mousemove", str(x), str(y), "click", "1")
        if d in ("dblclick", "dbl"):
            return xd("mousemove", str(x), str(y), "click", "--repeat", "2", "1")
        if d == "right":
            return xd("mousemove", str(x), str(y), "click", "3")
        if d == "type" or d == "text":
            return xd("type", "--delay", "12", "--", str(act.get("text") or act.get("txt") or ""))
        if d in ("key", "hotkey"):
            return xd("key", str(act.get("key") or act.get("combo") or act.get("k") or "Return"))
        return {"ok": False, "err": f"acao desconhecida: {d}"}
    S = PS_GUI
    if d == "move":
        S += f"[M]::SetCursorPos({x},{y})"
    elif d in ("click", "dblclick", "dbl", "right", "middle"):
        down, up = (2, 4) if d in ("click", "dblclick", "dbl") else ((8, 16) if d == "right" else (32, 64))
        S += f"[M]::SetCursorPos({x},{y});Start-Sleep -m 40;"
        S += f"[M]::mouse_event({down},0,0,0,0);[M]::mouse_event({up},0,0,0,0);"
        if d in ("dblclick", "dbl"):
            S += f"Start-Sleep -m 80;[M]::mouse_event({down},0,0,0,0);[M]::mouse_event({up},0,0,0,0);"
    elif d == "down":
        S += f"[M]::SetCursorPos({x},{y});[M]::mouse_event(2,0,0,0,0);"
    elif d == "up":
        S += f"[M]::SetCursorPos({x},{y});[M]::mouse_event(4,0,0,0,0);"
    elif d == "drag":
        x2, y2 = int(float(act.get("x2", 0) or 0)), int(float(act.get("y2", 0) or 0))
        S += (
            f"[M]::SetCursorPos({x},{y});Start-Sleep -m 50;[M]::mouse_event(2,0,0,0,0);"
            f"Start-Sleep -m 60;"
        )
        for i in range(1, 9):
            S += f"[M]::SetCursorPos({x + (x2 - x) * i // 8},{y + (y2 - y) * i // 8});Start-Sleep -m 16;"
        S += "[M]::mouse_event(4,0,0,0,0);"
    elif d == "scroll":
        amt = int(float(act.get("amount", act.get("dy", -400)) or -400))
        S += f"[M]::SetCursorPos({x},{y});[M]::mouse_event(2048,0,0,{amt & 0xFFFFFFFF},0);"
    elif d in ("type", "text"):
        S += f"[System.Windows.Forms.SendKeys]::SendWait({ps_str(sendkeys_escape(act.get('text') or act.get('txt') or ''))})"
    elif d == "key":
        S += f"[System.Windows.Forms.SendKeys]::SendWait({ps_str(act.get('key') or act.get('k') or '{ENTER}')})"
    elif d == "hotkey":
        S += f"[System.Windows.Forms.SendKeys]::SendWait({ps_str(act.get('combo') or '')})"
    else:
        return {"ok": False, "err": f"acao desconhecida: {d}"}
    try:
        out, err = ps(S, 20)
        return {"ok": not err.strip(), "out": out.strip()[:200], "err": err.strip()[:200] or None}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "err": str(e)}


APPS_WIN = {
    "roblox": [
        r"$env:LOCALAPPDATA\Roblox\Versions\*\RobloxStudioBeta.exe",
        r"$env:LOCALAPPDATA\Roblox\Versions\*\RobloxStudioLauncherBeta.exe",
        r"C:\Program Files (x86)\Roblox\Versions\*\RobloxStudioBeta.exe",
    ],
    "studio": [
        r"$env:LOCALAPPDATA\Roblox\Versions\*\RobloxStudioBeta.exe",
        r"$env:LOCALAPPDATA\Roblox\Versions\*\RobloxStudioLauncherBeta.exe",
    ],
    "blender": [r"C:\Program Files\Blender Foundation\*\blender.exe", "blender"],
    "explorer": ["explorer.exe"],
    "notepad": ["notepad.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "msedge.exe"],
    "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "chrome.exe"],
}


def abrir_app(nome: str, caminho: str | None = None) -> dict:
    nome = (nome or "").lower().strip()
    if nome in ("robloxstudio",):
        nome = "studio"
    if not IS_WIN:
        return {"ok": False, "err": "abrir app neste agente é Windows (Windows App / Studio)."}
    cands = [caminho] if caminho else APPS_WIN.get(nome)
    if not cands:
        return {"ok": False, "err": "não sei abrir %r. Conhecidos: %s" % (nome, ", ".join(APPS_WIN))}
    lista = ",".join(ps_str(c) for c in cands)
    script = f"""
$ok=$false
foreach($c in @({lista})){{
  $c2=$ExecutionContext.InvokeCommand.ExpandString($c)
  $p=$null
  if($c2 -match '[\\\\/]'){{ $p=Get-Item -Path $c2 -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName }}
  else {{ $p=(Get-Command $c2 -ErrorAction SilentlyContinue | Select-Object -First 1).Source; if(-not $p){{ $p=$c2 }} }}
  if($p){{ try {{ Start-Process $p; Write-Output "OK|$p"; $ok=$true; break }} catch {{ }} }}
}}
if(-not $ok){{ Write-Output "NAO|nenhum candidato existe" }}
"""
    try:
        out, err = ps(script, 40)
        ln = (out.strip().splitlines() or ["NAO|sem saida"])[-1]
        if ln.startswith("OK|"):
            return {"ok": True, "exe": ln[3:]}
        return {"ok": False, "err": f"{nome}: {ln[4:] if '|' in ln else ln} {err[:200]}".strip()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "err": str(e)}


def _ts_ip() -> str:
    exe = shutil.which("tailscale")
    if IS_WIN and not exe:
        p = Path(r"C:\Program Files\Tailscale\tailscale.exe")
        exe = str(p) if p.exists() else ""
    if not exe:
        return ""
    try:
        r = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True, timeout=12)
        return (r.stdout or "").strip().splitlines()[0] if r.stdout else ""
    except Exception:
        return ""


def machine() -> dict:
    return {
        "host": platform.node(),
        "os": "windows" if IS_WIN else platform.system().lower(),
        "sistema": platform.system(),
        "python": platform.python_version(),
        "uptime_s": int(time.time() - BOOT),
        "port": PORT,
        "cwd": str(WORK),
        "dsos": True,
    }


def autologon(username: str, password: str) -> dict:
    if not IS_WIN:
        return {"ok": False, "message": "Auto-logon é Windows (registry AutoAdminLogon)."}
    ps_script = r"""
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
            [PWSH, "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=30, env=env,
        )
        ok = r.returncode == 0 and "ARKHER_AUTOLOGON_OK" in (r.stdout or "")
        return {"ok": ok, "code": r.returncode, "out": (r.stdout or "")[-2000:], "err": (r.stderr or "")[-1000:]}
    except Exception as e:  # noqa: BLE001
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


def install_app(nome: str) -> dict:
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
                urllib.request.urlretrieve(  # noqa: S310
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
            return {"ok": r.returncode == 0, "app": "blender", "out": (r.stdout or r.stderr or "")[-1500:]}
        return {"ok": False, "message": "Blender: instale ou coloque no PATH. Sem winget neste PC."}
    return {"ok": False, "message": f"install não permitido: {nome}"}


def open_app(nome: str) -> dict:
    r = abrir_app(nome)
    if r.get("ok"):
        return r
    if nome.lower() in ("studio", "roblox", "robloxstudio", "blender"):
        inst = install_app(nome)
        r2 = abrir_app(nome)
        if r2.get("ok"):
            return r2
        return {"ok": False, "message": r.get("err") or r2.get("err"), "install": inst}
    return {"ok": False, "message": r.get("err") or "app não permitida"}


def _rbx_python_convert(src_p: Path, dest_p: Path) -> dict | None:
    here = Path(__file__).resolve()
    candidates = [here.parent, here.parents[2] if len(here.parents) >= 2 else here.parent]
    for root in candidates:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
    try:
        from backend.app.acervo.rbx_binary import convert_file  # type: ignore
    except Exception:
        return None
    convert_file(src_p, dest_p)
    return {"ok": True, "dest": str(dest_p), "modo": "arkher", "bytes": dest_p.stat().st_size}


def convert_rbx(src: str, dest: str | None = None) -> dict:
    src_p = Path(src)
    if not src_p.is_file():
        return {"ok": False, "message": "arquivo fonte inexistente"}
    dest_p = Path(dest) if dest else WORK / (src_p.stem + (".rbxlx" if src_p.suffix.lower() == ".rbxl" else ".rbxmx"))
    head = src_p.open("rb").read(80).lstrip()
    if head.startswith(b"<") and not head.startswith(b"<roblox!"):
        if src_p.resolve() != dest_p.resolve():
            shutil.copy2(src_p, dest_p)
        return {"ok": True, "dest": str(dest_p), "modo": "xml_copy", "bytes": dest_p.stat().st_size}
    try:
        got = _rbx_python_convert(src_p, dest_p)
        if got and dest_p.exists() and dest_p.stat().st_size > 40:
            return got
    except Exception as e:  # noqa: BLE001
        py_err = f"{type(e).__name__}: {e}"
    else:
        py_err = ""
    tool = shutil.which("rbx-util") or shutil.which("rbx-dom")
    if tool:
        r = subprocess.run([tool, "convert", str(src_p), str(dest_p)], capture_output=True, text=True, timeout=900)
        return {"ok": r.returncode == 0 and dest_p.exists(), "dest": str(dest_p), "out": (r.stdout or r.stderr or "")[-1000:]}
    return {"ok": False, "message": py_err or "conversor falhou no binário"}


def import_place(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "message": "place não encontrado"}
    if IS_WIN:
        os.startfile(str(p))  # noqa: S606
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


def ls(path: str | None = None) -> dict:
    p = Path(path) if path else WORK
    if not p.exists():
        return {"ok": False, "message": "path inexistente"}
    itens = []
    for c in sorted(p.iterdir())[:200]:
        itens.append({"nome": c.name, "dir": c.is_dir(), "bytes": c.stat().st_size if c.is_file() else 0})
    return {"ok": True, "path": str(p), "itens": itens}


def janelas() -> dict:
    if not IS_WIN:
        return {"ok": True, "janelas": []}
    out, err = ps(
        "Get-Process | Where-Object {$_.MainWindowTitle} | "
        "Select-Object -First 40 Id,ProcessName,MainWindowTitle | ConvertTo-Json -Compress",
        20,
    )
    try:
        data = json.loads(out or "[]")
        if isinstance(data, dict):
            data = [data]
        return {"ok": True, "janelas": data}
    except Exception:
        return {"ok": False, "err": err[:300] or out[:300]}


def run_job(kind: str, args: dict) -> dict:
    if kind == "screenshot":
        return screen_payload(0.5, 55)
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
        return do_input({"do": "click", "x": args.get("x", 0), "y": args.get("y", 0)})
    if kind == "type":
        return do_input({"do": "type", "text": str(args.get("text", ""))[:200]})
    if kind == "ls":
        return ls(args.get("path"))
    if kind in ("health", "status"):
        return {"ok": True, **machine()}
    return {"ok": False, "message": f"job desconhecido: {kind}"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[arkher-agent] " + (fmt % args) + "\n")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-store")

    def _json(self, code: int, payload: dict):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(raw)
        except Exception:
            pass

    def _jpeg(self, raw: bytes, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.send_header("X-Arkher-W", str(_LAST_JPEG["meta"].get("w") or 0))
        self.send_header("X-Arkher-H", str(_LAST_JPEG["meta"].get("h") or 0))
        self.send_header("X-Arkher-Real-W", str(_LAST_JPEG["meta"].get("real_w") or 0))
        self.send_header("X-Arkher-Real-H", str(_LAST_JPEG["meta"].get("real_h") or 0))
        self.send_header("X-Arkher-Title", str(_LAST_JPEG["meta"].get("titulo") or "")[:180])
        self.end_headers()
        try:
            self.wfile.write(raw)
        except Exception:
            pass

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    def do_OPTIONS(self):
        self._json(200, {"ok": True})

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = u.path.rstrip("/") or "/"
        if path in ("/", "/health", "/node"):
            info = machine()
            if path == "/node":
                info["tailscale_ip"] = _ts_ip()
                info["url"] = "http://%s:%s" % (info.get("tailscale_ip") or info.get("host"), PORT)
            return self._json(200, {"ok": True, **info})
        if path in ("/screen", "/dsos/screen"):
            sc = float((q.get("scale") or ["0.45"])[0])
            qa = int((q.get("q") or ["50"])[0])
            p = screen_payload(sc, qa)
            return self._json(200, p)
        if path in ("/frame", "/dsos/frame"):
            sc = float((q.get("scale") or q.get("s") or ["0.45"])[0])
            if sc > 1:
                sc = sc / 100.0
            qa = int((q.get("q") or ["50"])[0])
            p = screen_payload(sc, qa)
            if not p.get("ok"):
                return self._json(503, p)
            return self._jpeg(base64.b64decode(p["b64"]))
        if path in ("/guiready", "/dsos/guiready"):
            return self._json(200, gui_ready())
        if path in ("/janelas", "/dsos/janelas"):
            return self._json(200, janelas())
        if not _auth(self):
            return self._json(401, {"ok": False, "code": "UNAUTHORIZED"})
        return self._json(404, {"ok": False, "code": "NOT_FOUND"})

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            body = self._body()
        except Exception:
            return self._json(400, {"ok": False, "err": "json invalido"})
        if path in ("/input", "/dsos/input"):
            acts = body.get("acts") or body.get("eventos") or ([body] if (body.get("do") or body.get("t")) else [])
            res = []
            for a in acts[:40]:
                res.append(do_input(a if isinstance(a, dict) else {}))
            return self._json(200, {"ok": all(r.get("ok") for r in res) if res else False, "res": res})
        if not _auth(self):
            return self._json(401, {"ok": False, "code": "UNAUTHORIZED"})
        if path == "/autologon":
            return self._json(200, autologon(str(body.get("username", "")), str(body.get("password", ""))))
        if path == "/job":
            return self._json(200, run_job(str(body.get("kind", "")), body.get("args") or {}))
        if path in ("/app", "/abrir", "/dsos/abrir"):
            r = abrir_app(str(body.get("nome") or body.get("app") or body.get("bin") or ""), body.get("caminho"))
            return self._json(200 if r.get("ok") else 400, r)
        return self._json(404, {"ok": False, "code": "NOT_FOUND"})


def main() -> int:
    if not agent_token():
        print("sem token: tela e toque livres (como o agente antigo)", flush=True)
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    httpd.daemon_threads = True
    print(f"ARKHER agent+DsOS {PORT} host={platform.node()} win={IS_WIN}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
