"""Conversão e organização do acervo Roblox.

Padrão no celular:
  /storage/emulated/0/ArkherAITraining

- .rbxl  → .rbxlx (XML de place)
- .rbxm  → .rbxmx (XML de model)
- XML já existentes são copiados para pastas/subpastas
- Binário sem conversor: pendência honesta (nunca finge conversão)

A ARKHER lê os XML organizados para treino e para criar duas versões
(usuário + treino) no Studio do Workspace, com permissão.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

DEFAULT_ROOT = Path("/storage/emulated/0/ArkherAITraining")

EXTS = {".rbxl": "rbxl", ".rbxlx": "rbxlx", ".rbxm": "rbxm", ".rbxmx": "rbxmx"}
SKIP = {"_arkher", ".git", "node_modules"}

CATEGORIAS = (
    ("personagens", re.compile(r"(char|avatar|npc|rig|humanoide|person)", re.I)),
    ("mapas", re.compile(r"(map|place|obby|arena|base|city|cidade|world|praga|prague|florida)", re.I)),
    ("veiculos", re.compile(r"(car|jeep|tank|heli|bike|nave|ship)", re.I)),
    ("armas", re.compile(r"(gun|sword|arma|weapon|tool)", re.I)),
    ("animacao", re.compile(r"(anim|emote|idle|walk|run)", re.I)),
    ("ui", re.compile(r"(ui|hud|gui|menu)", re.I)),
    ("terreno", re.compile(r"(terrain|terreno|height)", re.I)),
)


def categoria(nome: str) -> str:
    for cat, rx in CATEGORIAS:
        if rx.search(nome):
            return cat
    return "outros"


GRANDE = 32 * 1024 * 1024  # não duplica place de dezenas/centenas de MB
HASH_CACHE = "hashes.json"


def _cache_path(folders: dict[str, Path]) -> Path:
    return folders["indices"] / HASH_CACHE


def _load_cache(folders: dict[str, Path]) -> dict:
    p = _cache_path(folders)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def digest_cached(p: Path, cache: dict) -> tuple[str, int]:
    st = p.stat()
    key = f"{p.resolve()}|{st.st_mtime_ns}|{st.st_size}"
    hit = cache.get(key)
    if hit and "sha" in hit:
        return hit["sha"], int(hit.get("bytes") or st.st_size)
    sha, n = digest(p)
    cache[key] = {"sha": sha, "bytes": n}
    return sha, n


def digest(p: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    with p.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
            n += len(b)
    return h.hexdigest(), n


def is_xml(p: Path) -> bool:
    try:
        return p.open("rb").read(240).lstrip().startswith(b"<")
    except OSError:
        return False


def convert_bin(src: Path, dst: Path, kind: str) -> tuple[bool, str]:
    template = os.environ.get("ARKHER_RBXL_CONVERTER", "").strip()
    if not template:
        return False, "conversor nao configurado (ARKHER_RBXL_CONVERTER)"
    cmd = template.format(input=str(src), output=str(dst), kind=kind)
    try:
        r = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=900,
        )
        if r.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            return True, "convertido"
        return False, (r.stdout or "falha do conversor")[-500:]
    except Exception as e:
        return False, str(e)


def pastas(root: Path) -> dict[str, Path]:
    store = root / "_arkher"
    out = {
        "originais": store / "originais",
        "pendencias": store / "pendencias",
        "previews": store / "previews",
        "indices": store / "indices",
        "treino": store / "treino",
        "usuario": store / "usuario",
        "xml_rbxlx": store / "xml" / "rbxlx",
        "xml_rbxmx": store / "xml" / "rbxmx",
    }
    for p in out.values():
        p.mkdir(parents=True, exist_ok=True)
    for cat in list({c for c, _ in CATEGORIAS}) + ["outros"]:
        (out["xml_rbxlx"] / cat).mkdir(parents=True, exist_ok=True)
        (out["xml_rbxmx"] / cat).mkdir(parents=True, exist_ok=True)
    return out


def _destino_xml(folders: dict[str, Path], src: Path, xml_kind: str, sha: str) -> Path:
    cat = categoria(src.stem)
    base = folders["xml_rbxlx" if xml_kind == "rbxlx" else "xml_rbxmx"]
    return base / cat / f"{sha[:16]}_{src.stem}.{xml_kind}"


def ingerir(root: Path | None = None) -> dict:
    root = Path(root) if root else DEFAULT_ROOT
    if not root.exists():
        return {"ok": False, "code": "ROOT_MISSING", "root": str(root), "arquivos": []}
    folders = pastas(root)
    cache = _load_cache(folders)
    records: list[dict] = []
    for src in sorted(root.rglob("*")):
        if not src.is_file() or any(part in SKIP for part in src.relative_to(root).parts):
            continue
        kind = EXTS.get(src.suffix.lower())
        if not kind:
            continue
        sha, size = digest_cached(src, cache)
        rec: dict = {
            "arquivo": str(src),
            "tipo": kind,
            "sha256": sha,
            "bytes": size,
            "mb": round(size / (1024 * 1024), 2),
            "grande": size >= GRANDE,
            "categoria": categoria(src.stem),
            "visto_em": time.time(),
        }
        original = folders["originais"] / f"{sha[:16]}_{src.name}"
        # place de 100 MB não é duplicado — o índice aponta o original
        if size < GRANDE and not original.exists():
            shutil.copy2(src, original)
        rec["original"] = str(original) if original.exists() else str(src)
        xml_kind = "rbxlx" if kind in ("rbxl", "rbxlx") else "rbxmx"
        target = _destino_xml(folders, src, xml_kind, sha)
        if kind in ("rbxlx", "rbxmx") or is_xml(src):
            if size >= GRANDE:
                rec["xml"] = str(src)
                rec["conversao"] = {"ok": True, "mensagem": "xml_no_lugar"}
            else:
                if not target.exists():
                    shutil.copy2(src, target)
                rec["xml"] = str(target)
                rec["conversao"] = {"ok": True, "mensagem": "xml"}
        else:
            if not target.exists():
                ok, msg = convert_bin(src, target, kind)
                rec["conversao"] = {"ok": ok, "mensagem": msg, "destino": str(target)}
                if not ok:
                    (folders["pendencias"] / f"{sha[:16]}.json").write_text(
                        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
            rec["xml"] = str(target) if target.exists() else None
        records.append(rec)
    manifest = {
        "schema": "arkher-ingest-v2",
        "root": str(root),
        "atualizado": time.time(),
        "arquivos": records,
        "xml_rbxlx": sum(1 for r in records if r.get("xml") and str(r["xml"]).endswith(".rbxlx")),
        "xml_rbxmx": sum(1 for r in records if r.get("xml") and str(r["xml"]).endswith(".rbxmx")),
        "pendencias": sum(1 for r in records if not r.get("xml")),
        "gigantes": sum(1 for r in records if r.get("grande")),
        "bytes_total": sum(int(r.get("bytes") or 0) for r in records),
    }
    (folders["indices"] / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _cache_path(folders).write_text(json.dumps(cache), encoding="utf-8")
    return {"ok": True, **manifest}


def ler_xml(path: Path, limite: int = 80_000) -> dict:
    with path.open("rb") as f:
        text = f.read(limite).decode("utf-8", errors="replace")
    scripts = re.findall(r"<ProtectedString[^>]*>(.*?)</ProtectedString>", text, re.S)
    classes = re.findall(r'class="([^"]+)"', text)
    nomes = re.findall(r'<string name="Name">([^<]+)</string>', text)
    return {
        "arquivo": str(path),
        "caracteres": len(text),
        "classes": sorted(set(classes))[:80],
        "instancias": len(classes),
        "nomes": nomes[:80],
        "scripts": len(scripts),
        "amostra": text[:4000],
    }


def listar_xml(root: Path | None = None) -> list[dict]:
    root = Path(root) if root else DEFAULT_ROOT
    store = root / "_arkher" / "xml"
    out: list[dict] = []
    if not store.exists():
        return out
    for p in sorted(store.rglob("*")):
        if p.suffix.lower() in (".rbxlx", ".rbxmx"):
            out.append(
                {
                    "path": str(p),
                    "tipo": p.suffix.lower()[1:],
                    "categoria": p.parent.name,
                    "bytes": p.stat().st_size,
                }
            )
    return out
