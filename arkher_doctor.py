#!/usr/bin/env python3
"""Preflight reproduzível para uma instalação ARKHER.

O doctor não declara que um jogo foi construído, renderizado ou jogado. Ele
verifica somente pré-condições observáveis: arquivos do checkout, Python/Node,
espaço e escrita do estado, autenticação/configuração, estado persistido e,
quando solicitado, a disponibilidade dos executáveis/endpoint. Use-o antes de
subir um agente ou um worker e guarde a saída JSON junto do run.

Exemplos:
  python3 arkher_doctor.py --json
  python3 arkher_doctor.py --agent http://127.0.0.1:8765 --token "$ARKHER_AGENT_TOKEN"
  python3 arkher_doctor.py --engines blender godot --require-engines
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


REQUIRED = (
    "agent.py",
    "arkher_station_worker.py",
    "arkher_station.js",
    "arkher_station_ui.js",
    "COMO-USAR.txt",
)
ENGINE_COMMANDS = {
    "blender": (("blender", "--version"),),
    "godot": (("godot", "--version"), ("godot4", "--version")),
    "unity": (("unity", "-version"), ("Unity", "-version")),
    "unreal": (("UnrealEditor-Cmd", "-version"), ("UnrealEditor", "-version"),
               ("RunUAT", "-Help"), ("RunUAT.bat", "-Help")),
}


def _result(name, status, detail, **extra):
    out = {"name": name, "status": status, "detail": str(detail)[:1000]}
    out.update(extra)
    return out


def _run(argv, timeout=8):
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL)
        return p.returncode, (p.stdout or "")[-2000:]
    except FileNotFoundError:
        return 127, "não encontrado"
    except Exception as exc:
        return 125, "%s: %s" % (type(exc).__name__, exc)


def _writable(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    marker = path / (".arkher-doctor-%d-%s" % (os.getpid(), int(time.time() * 1000)))
    try:
        with marker.open("w", encoding="utf-8") as f:
            f.write("ok\n")
            f.flush()
            os.fsync(f.fileno())
        marker.unlink()
        return True, "diretório gravável"
    except Exception as exc:
        try:
            marker.unlink(missing_ok=True)
        except Exception:
            pass
        return False, "%s: %s" % (type(exc).__name__, exc)


def _state_size(path, cap=2 * 1024 * 1024 * 1024):
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            dirs[:] = [x for x in dirs if x not in (".git", "__pycache__")]
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
                if total >= cap:
                    return total
    except OSError:
        pass
    return total


def _check_source(root):
    checks = []
    for rel in REQUIRED:
        path = root / rel
        checks.append(_result("file:%s" % rel, "ok" if path.is_file() else "fail",
                              "presente" if path.is_file() else "ausente"))
    for path in sorted(root.glob("*.py")):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
            checks.append(_result("pycompile:%s" % path.name, "ok", "compila"))
        except Exception as exc:
            checks.append(_result("pycompile:%s" % path.name, "fail", str(exc)))
    node = shutil.which("node")
    if node:
        for path in sorted(root.glob("*.js")):
            code, out = _run([node, "--check", str(path)])
            checks.append(_result("nodecheck:%s" % path.name, "ok" if code == 0 else "fail",
                                  "sintaxe válida" if code == 0 else out))
    else:
        checks.append(_result("node", "warn", "node não está instalado; checks JavaScript não executados"))
    return checks


def _check_state(state, min_free_gb):
    checks = []
    ok, detail = _writable(state)
    checks.append(_result("state:writable", "ok" if ok else "fail", detail))
    try:
        usage = shutil.disk_usage(state)
        free_gb = usage.free / 1e9
        status = "ok" if free_gb >= min_free_gb else "fail"
        checks.append(_result("state:disk", status,
                              "%.2f GB livres de %.2f GB" % (free_gb, usage.total / 1e9),
                              freeBytes=usage.free, totalBytes=usage.total))
    except Exception as exc:
        checks.append(_result("state:disk", "fail", str(exc)))
    station = Path(state) / "station.json"
    if station.exists():
        try:
            data = json.loads(station.read_text(encoding="utf-8"))
            valid = isinstance(data, dict) and isinstance(data.get("jobs", []), list)
            checks.append(_result("state:station", "ok" if valid else "fail",
                                  "JSON válido" if valid else "schema básico inválido"))
        except Exception as exc:
            checks.append(_result("state:station", "fail",
                                  "não será sobrescrito automaticamente: %s" % exc))
    else:
        checks.append(_result("state:station", "ok", "ainda não criado"))
    checks.append(_result("state:size", "ok", "%d bytes observados" % _state_size(state),
                          bytes=_state_size(state)))
    return checks


def _check_auth(token, allow_insecure, require_token):
    configured = bool(str(token or "").strip())
    checks = []
    if configured and len(str(token).strip()) >= 20:
        checks.append(_result("auth:token", "ok", "token configurado; comprimento não exposto",
                              configured=True))
    elif configured:
        checks.append(_result("auth:token", "warn", "token configurado, mas tem menos de 20 caracteres",
                              configured=True))
    elif allow_insecure or not require_token:
        checks.append(_result("auth:token", "warn",
                              "modo sem token explicitamente permitido; restrinja a localhost/rede confiável",
                              configured=False))
    else:
        checks.append(_result("auth:token", "fail",
                              "ARKHER_AGENT_TOKEN ausente; o padrão seguro exige Bearer",
                              configured=False))
    return checks


def _check_engines(names, required):
    checks = []
    for name in names:
        key = name.lower()
        if key == "roblox":
            checks.append(_result("engine:roblox", "warn",
                                  "Studio/login/GUI precisam de observação real; doctor não testa headless"))
            continue
        candidates = ENGINE_COMMANDS.get(key)
        if not candidates:
            checks.append(_result("engine:%s" % key, "fail", "engine desconhecida"))
            continue
        found = None
        output = ""
        for argv in candidates:
            exe = shutil.which(argv[0])
            if not exe:
                continue
            code, output = _run([exe, *argv[1:]], timeout=15)
            found = exe
            if code == 0:
                break
        if found and code == 0:
            checks.append(_result("engine:%s" % key, "ok", "%s respondeu: %s" %
                                  (found, " ".join(output.strip().splitlines()[:2]))))
        elif found:
            checks.append(_result("engine:%s" % key, "warn" if not required else "fail",
                                  "%s encontrado, mas comando de versão falhou: %s" % (found, output)))
        else:
            checks.append(_result("engine:%s" % key, "fail" if required else "warn",
                                  "executável não encontrado; receitas não foram executadas"))
    return checks


def _check_agent(url, token):
    if not url:
        return []
    base = str(url).rstrip("/")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + str(token)
    checks = []
    for route in ("/health", "/ready"):
        req = urllib.request.Request(base + route, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as res:
                raw = res.read(512 * 1024)
                data = json.loads(raw.decode("utf-8"))
                status = res.status
        except urllib.error.HTTPError as exc:
            status = exc.code
            try:
                data = json.loads(exc.read(512 * 1024).decode("utf-8"))
            except Exception:
                data = {}
        except Exception as exc:
            checks.append(_result("agent:%s" % route, "fail", str(exc)))
            continue
        if route == "/health":
            good = status == 200 and data.get("ok") is True
            detail = ("respondeu; ready=%s authConfigured=%s" %
                      (data.get("ready"), data.get("auth_configured")))
        else:
            good = status == 200 and data.get("ready") is True
            detail = "HTTP %s; ready=%s" % (status, data.get("ready"))
        checks.append(_result("agent:%s" % route, "ok" if good else "fail", detail,
                              httpStatus=status))
    return checks


def run(args):
    root = Path(args.root).expanduser().resolve()
    state = Path(args.state).expanduser().resolve()
    token = args.token or os.environ.get("ARKHER_AGENT_TOKEN", "")
    allow_insecure = args.allow_insecure or os.environ.get("ARKHER_ALLOW_INSECURE", "").lower() in ("1", "true", "yes", "on")
    require_token = os.environ.get("ARKHER_REQUIRE_TOKEN", "1").lower() not in ("0", "false", "no", "off")
    checks = []
    py_ok = sys.version_info >= (3, 9)
    checks.append(_result("python", "ok" if py_ok else "fail", platform.python_version()))
    checks.extend(_check_source(root))
    checks.extend(_check_state(state, args.min_free_gb))
    checks.extend(_check_auth(token, allow_insecure, require_token))
    if not os.environ.get("ARKHER_CORS_ORIGINS") and not allow_insecure:
        checks.append(_result("cors", "warn", "ARKHER_CORS_ORIGINS vazio: browsers cross-origin serão bloqueados por segurança"))
    if args.engines:
        checks.extend(_check_engines(args.engines, args.require_engines))
    checks.extend(_check_agent(args.agent, token))
    failures = [x for x in checks if x["status"] == "fail"]
    warnings = [x for x in checks if x["status"] == "warn"]
    return {"ok": not failures and (not warnings or not args.strict),
            "root": str(root), "state": str(state), "checks": checks,
            "summary": {"ok": len(checks) - len(failures) - len(warnings),
                        "warn": len(warnings), "fail": len(failures)},
            "observedAt": time.time()}


def main(argv=None):
    ap = argparse.ArgumentParser(description="preflight seguro e observável do ARKHER")
    default_root = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--root", default=default_root)
    ap.add_argument("--state", default=os.environ.get("ARKHER_STATE") or
                    os.path.join(default_root, "arkher_state"))
    ap.add_argument("--agent", default="", help="URL opcional para testar /health e /ready")
    ap.add_argument("--token", default=os.environ.get("ARKHER_AGENT_TOKEN", ""))
    ap.add_argument("--allow-insecure", action="store_true",
                    help="aceita explicitamente instalação sem token; gera warning")
    ap.add_argument("--min-free-gb", type=float, default=1.0)
    ap.add_argument("--engines", nargs="*", choices=("blender", "godot", "unity", "unreal", "roblox"))
    ap.add_argument("--require-engines", action="store_true")
    ap.add_argument("--strict", action="store_true", help="warnings também fazem o preflight falhar")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)
    report = run(args)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("ARKHER DOCTOR — %s" % ("OK" if report["ok"] else "FALHA"))
        for item in report["checks"]:
            print("[%s] %-28s %s" % (item["status"].upper(), item["name"], item["detail"]))
        print("Resumo: %s" % json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
