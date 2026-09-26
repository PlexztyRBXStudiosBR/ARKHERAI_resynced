"""Figma → HUD Roblox. Token do usuário; sem token, kit próprio (não inventa o arquivo)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from xml.sax.saxutils import escape


def _hud(nomes: list[str], seed: int) -> str:
    botoes = "\n".join(
        f'  <Item class="TextButton"><Properties>'
        f'<string name="Name">{escape(n[:40] or "Btn")}</string>'
        f'<UDim2 name="Size"><X><S>0.2</S></X><Y><S>0.08</S></Y></UDim2>'
        f"</Properties></Item>"
        for n in (nomes or ["Jogar", "Opções", "Sair"])[:12]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<roblox version="4">\n'
        '<Item class="ScreenGui" referent="g1"><Properties>'
        f'<string name="Name">ARKHER_Figma_{seed}</string>'
        "</Properties>\n"
        f"{botoes}\n"
        "</Item></roblox>\n"
    )


def _walk(node: dict, acc: list[str]) -> None:
    name = str(node.get("name") or "")
    typ = str(node.get("type") or "")
    if typ in {"FRAME", "COMPONENT", "INSTANCE", "TEXT"} and name:
        acc.append(name)
    for ch in node.get("children") or []:
        if isinstance(ch, dict):
            _walk(ch, acc)


def de_json(doc: dict, seed: int = 1) -> dict:
    nomes: list[str] = []
    docu = doc.get("document") if isinstance(doc, dict) else None
    if isinstance(docu, dict):
        _walk(docu, nomes)
    xml = _hud(nomes, seed)
    return {
        "descricao": f"HUD a partir do Figma ({len(nomes)} frames/textos). Sem modelo de IA de terceiro.",
        "arquivo": {"nome": f"arkher_figma_{seed}.rbxmx", "conteudo": xml},
        "como_usar": "Importe no Studio (StarterGui) ou mande ao Workspace.",
        "frames": nomes[:40],
    }


def puxar(file_key: str, token: str, seed: int = 1) -> dict:
    key = (file_key or "").strip()
    tok = (token or os.environ.get("ARKHER_FIGMA_TOKEN") or "").strip()
    if not tok:
        return {
            "ok": False,
            "code": "SEM_TOKEN",
            "message": "Autorize o Figma em Integrações (token figd_…). Sem token eu não invento o arquivo.",
            **de_json({"document": {"children": [{"type": "TEXT", "name": "Jogar"}, {"type": "TEXT", "name": "Sair"}]}}, seed),
            "modo": "kit_proprio",
        }
    if not key:
        return {"ok": False, "code": "SEM_FILE", "message": "Passe a key do arquivo Figma (figma.com/file/KEY/...)."}
    req = urllib.request.Request(
        f"https://api.figma.com/v1/files/{key}",
        headers={"X-Figma-Token": tok},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            doc = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "code": f"HTTP_{e.code}", "message": f"Figma HTTP {e.code}."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "code": "FIGMA_OFF", "message": str(e)}
    out = de_json(doc, seed)
    out["ok"] = True
    out["modo"] = "figma_api"
    return out
