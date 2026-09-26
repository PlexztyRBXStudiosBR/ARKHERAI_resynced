"""Provas simuladas 2D/3D/Luau — o que um lead rodaria antes do playtest.

Determinístico. Sem motor Roblox. Cada professor da linhagem 'assina'
o laudo (não entra no chat). Treino só depois: estas provas é que
ensinam o próximo modelo o que passou/falhou.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from model.training.professores import listar as listar_professores


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def prova_xml(xml: str) -> dict:
    classes = re.findall(r'class="([^"]+)"', xml)
    parts = classes.count("Part") + classes.count("MeshPart") + classes.count("WedgePart")
    spawn = "SpawnLocation" in classes or "Spawn" in xml
    luz = any(c in classes for c in ("PointLight", "SpotLight", "SurfaceLight", "Sky"))
    scripts = sum(classes.count(c) for c in ("Script", "LocalScript", "ModuleScript"))
    # 3D: bounding boxes from size tags
    sizes = re.findall(r"<X>([0-9.eE+-]+)</X><Y>([0-9.eE+-]+)</Y><Z>([0-9.eE+-]+)</Z>", xml)
    nan = any(not math.isfinite(float(a)) for t in sizes for a in t)
    volume = 0.0
    for x, y, z in sizes[:400]:
        volume += abs(float(x) * float(y) * float(z))
    falhas = []
    if parts < 3:
        falhas.append("place pobre demais para um jogo (poucas Parts)")
    if not spawn:
        falhas.append("sem spawn visível")
    if nan:
        falhas.append("CFrame/size não finito")
    if volume > 1e9:
        falhas.append("escala absurda (void/mapa infinito acidental)")
    return {
        "tipo": "3d_estrutural",
        "parts": parts,
        "spawn": spawn,
        "luz": luz,
        "scripts": scripts,
        "volume": round(volume, 2),
        "ok": not falhas,
        "falhas": falhas,
    }


def prova_ui(xml: str) -> dict:
    """2D: botões sem overlap óbvio, sem cantos 'IA' (UICorner 12+ / fonte Inter)."""
    corners = [int(x) for x in re.findall(r'UICorner[^>]*>.*?CornerRadius[^0-9]*([0-9]+)', xml, re.S)]
    inter = bool(re.search(r"\bInter\b|\bRoboto\b|\bPoppins\b", xml))
    botoes = xml.count("TextButton") + xml.count("ImageButton")
    falhas = []
    if any(c >= 12 for c in corners):
        falhas.append("UICorner estilo SaaS/IA — ARKHER usa canto vivo (0–4)")
    if inter:
        falhas.append("fonte de IA genérica (Inter/Roboto/Poppins)")
    if botoes == 0:
        falhas.append("HUD sem ação")
    return {"tipo": "2d_hud", "botoes": botoes, "ok": not falhas, "falhas": falhas}


def prova_luau(src: str) -> dict:
    falhas = []
    if re.search(r"Loadstring|getfenv|setmetatable\(\s*_G", src, re.I):
        falhas.append("API perigosa")
    if "FireServer" in src and "OnServerEvent" not in src:
        falhas.append("cliente dispara sem servidor ouvir (neste arquivo)")
    if len(src.splitlines()) < 4:
        falhas.append("script vazio demais")
    remotes = len(re.findall(r"RemoteEvent|RemoteFunction", src))
    return {"tipo": "luau", "linhas": len(src.splitlines()), "remotes": remotes, "ok": not falhas, "falhas": falhas}


def assinar(laudo: dict) -> dict:
    """Cada professor no disco vê o laudo — não responde no chat."""
    profs = listar_professores().get("professores") or []
    assinaturas = []
    blob = json.dumps(laudo, sort_keys=True)
    for p in profs:
        if not p.get("ok"):
            continue
        assinaturas.append({
            "professor": p.get("nome"),
            "voto": "passa" if laudo.get("ok") else "reprova",
            "hash": _sha(blob + str(p.get("path"))),
            "chat": False,
        })
    laudo["professores"] = assinaturas
    return laudo


def rodar(arquivos: list[dict]) -> dict:
    provas = []
    for arq in arquivos:
        nome = str(arq.get("nome") or "")
        corpo = str(arq.get("conteudo") or "")
        if nome.endswith((".rbxlx", ".rbxmx", ".xml")):
            if "ScreenGui" in corpo or "TextButton" in corpo:
                provas.append(prova_ui(corpo))
            else:
                provas.append(prova_xml(corpo))
        elif nome.endswith((".lua", ".luau")):
            provas.append(prova_luau(corpo))
    ok = all(p.get("ok") for p in provas) if provas else False
    laudo = {"ok": ok, "provas": provas, "n": len(provas)}
    return assinar(laudo)
