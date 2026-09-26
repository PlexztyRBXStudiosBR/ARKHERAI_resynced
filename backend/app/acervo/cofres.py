"""Vários storages confiáveis — só o que o usuário autorizar por caminho local.

Não sobe o .rbxl de 100 MB pra nuvem sozinho. Espelha o *conhecimento*
(JSON + amostra de treino + hashes). Destinos:
  - data/cofres/local
  - acervo _arkher/treino (celular)
  - pastas extras em ARKHER_COFRES (separadas por :)
  - workers/sync (HF privado, se o dono rodar o push)
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from backend.app import config
from model.training.common import CHECKPOINT_DIR, GENERATED_DIR, ROOT


def destinos(acervo_root: Path | None = None) -> list[dict]:
    extra = [p.strip() for p in os.environ.get("ARKHER_COFRES", "").split(":") if p.strip()]
    roots = [
        ("local", config.DATA_DIR / "cofres" / "local"),
        ("treino_modelo", GENERATED_DIR / "treino"),
        ("hashes", CHECKPOINT_DIR),
    ]
    if acervo_root:
        roots.append(("celular", Path(acervo_root) / "_arkher" / "treino"))
    for i, p in enumerate(extra):
        roots.append((f"extra_{i}", Path(p)))
    out = []
    for nome, path in roots:
        try:
            path.mkdir(parents=True, exist_ok=True)
            ok = os.access(path, os.W_OK)
        except OSError:
            ok = False
        out.append({"id": nome, "path": str(path), "ok": ok})
    hf = ROOT / "workers" / "sync" / "hf_sync.py"
    out.append({"id": "hf_privado", "path": str(hf), "ok": hf.exists(), "nota": "push manual com sua permissão"})
    return out


def espelhar(arquivo: Path, acervo_root: Path | None = None) -> dict:
    """Copia um JSON/txt compacto para todo cofre gravável. Recusa binário enorme."""
    if not arquivo.is_file():
        return {"ok": False, "message": "arquivo inexistente"}
    if arquivo.stat().st_size > 2 * 1024 * 1024:
        return {"ok": False, "message": "cofre só leva conhecimento compacto (<2MB), não o place de 100MB"}
    feitos = []
    for d in destinos(acervo_root):
        if not d["ok"] or d["id"] in {"hashes", "hf_privado"}:
            continue
        alvo = Path(d["path"]) / arquivo.name
        try:
            shutil.copy2(arquivo, alvo)
            feitos.append({"cofre": d["id"], "path": str(alvo)})
        except OSError as e:
            feitos.append({"cofre": d["id"], "ok": False, "message": str(e)})
    return {"ok": True, "copias": feitos, "ativos": sum(1 for x in destinos(acervo_root) if x["ok"])}


def resumo(acervo_root: Path | None = None) -> dict:
    ds = destinos(acervo_root)
    return {"ok": True, "cofres": ds, "ativos": sum(1 for d in ds if d["ok"])}
