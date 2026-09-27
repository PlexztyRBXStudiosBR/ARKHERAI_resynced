"""Modelos 3D licenciados para o treino: Poly Haven (CC0), Sketchfab (token + downloadable).

Mixamo não tem API pública — a ARKHER NÃO faz scrape. Ingere FBX que VOCÊ baixou
em ArkherAITraining/mixamo, ou abre o site no PC virtual.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from backend.app import config

_UA = "ArkherAI/0.2 (treino educacional; https://github.com/PlexztyRBXStudiosBR/ARKHERAI_resynced)"
TIMEOUT = 25.0
MAX_ARQ = 12
MAX_BYTES = 25 * 1024 * 1024


def _dest() -> Path:
    d = config.DATA_DIR / "generated" / "treino" / "modelos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _http(url: str, headers: dict | None = None, timeout: float = TIMEOUT) -> bytes:
    h = {"User-Agent": _UA, **(headers or {})}
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read(MAX_BYTES + 1)


def _http_json(url: str, headers: dict | None = None) -> dict | list:
    return json.loads(_http(url, headers).decode("utf-8"))


def polyhaven_buscar(consulta: str, limite: int = 8) -> dict:
    consulta = (consulta or "character").strip()[:80]
    try:
        brutos = _http_json("https://api.polyhaven.com/assets?t=models")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return {"ok": False, "fonte": "polyhaven", "code": "FONTE_INDISPONIVEL", "message": str(e)}
    if not isinstance(brutos, dict):
        return {"ok": False, "fonte": "polyhaven", "code": "FONTE_INDISPONIVEL", "message": "resposta inesperada"}
    q = consulta.lower()
    hits = []
    for aid, meta in brutos.items():
        if not isinstance(meta, dict):
            continue
        blob = " ".join([aid, str(meta.get("name") or ""), " ".join(meta.get("tags") or [])]).lower()
        if q not in blob and not any(p in blob for p in q.split()):
            continue
        hits.append({"id": aid, "nome": meta.get("name") or aid, "tags": meta.get("tags") or [], "licenca": "CC0"})
        if len(hits) >= max(1, min(MAX_ARQ, limite)):
            break
    if not hits:
        # pega os primeiros CC0 mesmo sem match — treino precisa de volume
        for aid, meta in list(brutos.items())[: max(1, min(6, limite))]:
            if isinstance(meta, dict):
                hits.append({"id": aid, "nome": meta.get("name") or aid, "tags": meta.get("tags") or [], "licenca": "CC0"})
    return {"ok": True, "fonte": "polyhaven", "consulta": consulta, "resultados": hits, "atribuicao": "Poly Haven CC0"}


def polyhaven_baixar(asset_id: str) -> dict:
    aid = re.sub(r"[^a-zA-Z0-9_\\-]", "", asset_id)[:80]
    if not aid:
        return {"ok": False, "message": "id vazio"}
    try:
        files = _http_json(f"https://api.polyhaven.com/files/{aid}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return {"ok": False, "code": "FONTE_INDISPONIVEL", "message": str(e)}
    url = ""
    # gltf 1k preferido
    gltf = files.get("gltf") if isinstance(files, dict) else None
    if isinstance(gltf, dict):
        for res in ("1k", "2k", "4k"):
            bloco = gltf.get(res)
            if isinstance(bloco, dict):
                inner = bloco.get("gltf") or bloco.get("glb") or bloco
                if isinstance(inner, dict) and inner.get("url"):
                    url = str(inner["url"])
                    break
    if not url:
        return {"ok": False, "message": f"sem gltf público em {aid}"}
    try:
        raw = _http(url, timeout=60)
    except (urllib.error.URLError, TimeoutError) as e:
        return {"ok": False, "code": "FONTE_INDISPONIVEL", "message": str(e)}
    if len(raw) > MAX_BYTES:
        return {"ok": False, "message": "arquivo > 25MB, pulado"}
    dest = _dest() / f"polyhaven_{aid}.glb"
    # pode ser gltf zip-ish; grava bytes
    dest.write_bytes(raw)
    meta = {"fonte": "polyhaven", "id": aid, "licenca": "CC0", "bytes": dest.stat().st_size, "url": url}
    (dest.with_suffix(".json")).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, **meta, "path": str(dest)}


def sketchfab_buscar(consulta: str, token: str = "", limite: int = 8) -> dict:
    q = urllib.parse.quote((consulta or "game ready").strip()[:80])
    url = (
        f"https://api.sketchfab.com/v3/search?type=models&q={q}"
        f"&downloadable=true&restricted=0&count={max(1, min(MAX_ARQ, limite))}"
    )
    headers = {}
    tok = token or os.environ.get("ARKHER_SKETCHFAB_TOKEN") or ""
    if tok:
        headers["Authorization"] = "Token " + tok
    try:
        data = _http_json(url, headers)
    except urllib.error.HTTPError as e:
        return {"ok": False, "fonte": "sketchfab", "code": "HTTP", "message": f"Sketchfab HTTP {e.code}"}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return {"ok": False, "fonte": "sketchfab", "code": "FONTE_INDISPONIVEL", "message": str(e)}
    results = []
    for it in (data.get("results") or []) if isinstance(data, dict) else []:
        lic = ((it.get("license") or {}) if isinstance(it.get("license"), dict) else {}) 
        results.append({
            "id": it.get("uid"),
            "nome": it.get("name"),
            "url": (it.get("viewerUrl") or it.get("uri") or ""),
            "licenca": lic.get("slug") or lic.get("label") or "ver_pagina",
            "downloadable": bool(it.get("isDownloadable")),
        })
    return {
        "ok": True,
        "fonte": "sketchfab",
        "consulta": consulta,
        "resultados": results,
        "download": "só com token + licença downloadable. Sem scrape.",
        "atribuicao": "Sketchfab — respeite a licença de cada item.",
    }


def mixamo_nota() -> dict:
    return {
        "ok": True,
        "fonte": "mixamo",
        "download": False,
        "message": (
            "Mixamo (Adobe) não tem API pública. A ARKHER não entra na sua conta nem raspa o site. "
            "Baixe os FBX no navegador (HUD → Mixamo) e jogue em "
            "C:\\\\Users\\\\nexus\\\\ArkherAITraining\\\\mixamo — depois: 'ingere mixamo'."
        ),
    }


def ingerir_pasta(pasta: str | None = None) -> dict:
    """FBX/GLB/OBJ que a usuária já baixou (Mixamo, Sketchfab, etc.)."""
    candidatos = []
    if pasta:
        candidatos.append(Path(pasta))
    home = Path(r"C:\Users\nexus")
    candidatos += [
        home / "ArkherAITraining" / "mixamo",
        home / "ArkherAITraining" / "modelos",
        home / "Documents" / "ArkherAITraining" / "mixamo",
        Path("/storage/emulated/0/ArkherAITraining/mixamo"),
    ]
    exts = {".fbx", ".glb", ".gltf", ".obj", ".blend"}
    dest = _dest()
    copiados = []
    for root in candidatos:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                alvo = dest / p.name
                if not alvo.exists():
                    alvo.write_bytes(p.read_bytes()[:MAX_BYTES])
                copiados.append(str(alvo))
                if len(copiados) >= 80:
                    break
    return {"ok": True, "n": len(copiados), "pasta": str(dest), "arquivos": copiados[:40]}


def colher(consulta: str, token_sketchfab: str = "", baixar: bool = True, limite: int = 6) -> dict:
    """Busca + download CC0 (Poly Haven) + índice Sketchfab. Mixamo só nota/ingest."""
    ph = polyhaven_buscar(consulta, limite=limite)
    baixados = []
    if baixar and ph.get("ok"):
        for hit in (ph.get("resultados") or [])[:limite]:
            r = polyhaven_baixar(str(hit.get("id") or ""))
            baixados.append(r)
    sk = sketchfab_buscar(consulta, token_sketchfab, limite=limite)
    mx = mixamo_nota()
    ing = ingerir_pasta()
    ok_n = sum(1 for b in baixados if b.get("ok"))
    return {
        "ok": True,
        "consulta": consulta,
        "polyhaven": ph,
        "baixados": baixados,
        "sketchfab": sk,
        "mixamo": mx,
        "ingest_local": ing,
        "para_treino": ok_n + int(ing.get("n") or 0),
        "message": (
            f"Poly Haven CC0: {ok_n} baixados. Sketchfab: lista (download com token). "
            f"Mixamo: {ing.get('n') or 0} FBX locais. Tudo no Vault/treino."
        ),
    }
