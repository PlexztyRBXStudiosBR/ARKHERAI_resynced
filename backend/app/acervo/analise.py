"""Analisa rbxlx/rbxmx (e aponta binário) sem carregar jogo de 100 MB na RAM.

Para XML grande: varredura em blocos de 1 MB — classes, nomes, remotes, scripts.
Não é cópia do arquivo; é o grafo compacto que o próximo modelo treina.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import iterparse

SKIP = {".git", ".venv", "node_modules", "dist", "build", "__pycache__", "_arkher"}
XML_EXT = {".rbxlx", ".rbxmx", ".xml"}
BIN_EXT = {".rbxl", ".rbxm"}
LUA_EXT = {".lua", ".luau"}
GRANDE = 32 * 1024 * 1024  # 32 MB: não duplica, não parseia árvore inteira
ENORME = 100 * 1024 * 1024


def sha_arquivo(p: Path, bloco: int = 1024 * 1024) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    with p.open("rb") as f:
        while True:
            b = f.read(bloco)
            if not b:
                break
            h.update(b)
            n += len(b)
    return h.hexdigest(), n


def _head_text(p: Path, n: int = 240) -> bytes:
    with p.open("rb") as f:
        return f.read(n)


def e_xml(p: Path) -> bool:
    try:
        return _head_text(p).lstrip().startswith(b"<")
    except OSError:
        return False


def _scan_blocos(p: Path) -> dict:
    """Varredura 1 MB: aguenta place de +100 MB (Praga, Flórida, pack)."""
    classes: Counter[str] = Counter()
    nomes: list[str] = []
    remotes: list[str] = []
    scripts = 0
    source_chars = 0
    materiais: Counter[str] = Counter()
    resto = ""
    with p.open("rb") as f:
        while True:
            raw = f.read(1024 * 1024)
            if not raw:
                break
            trecho = resto + raw.decode("utf-8", errors="replace")
            resto = trecho[-200:] if len(trecho) > 200 else ""
            for m in re.finditer(r'class="([^"]+)"', trecho):
                classes[m.group(1)] += 1
            if len(nomes) < 400:
                for m in re.finditer(r'<string name="Name">([^<]{1,80})</string>', trecho):
                    nomes.append(m.group(1))
                    if len(nomes) >= 400:
                        break
            for m in re.finditer(r'class="(RemoteEvent|RemoteFunction|BindableEvent|BindableFunction)"', trecho):
                remotes.append(m.group(1))
            scripts += trecho.count('class="Script"') + trecho.count('class="LocalScript"') + trecho.count(
                'class="ModuleScript"'
            )
            source_chars += trecho.count("<ProtectedString")
            for m in re.finditer(r'<token name="Material">([^<]+)</token>', trecho):
                materiais[m.group(1)] += 1
    sistemas = {
        "workspace": classes.get("Workspace", 0),
        "parts": classes.get("Part", 0) + classes.get("MeshPart", 0) + classes.get("WedgePart", 0),
        "models": classes.get("Model", 0),
        "scripts": scripts,
        "gui": classes.get("ScreenGui", 0) + classes.get("BillboardGui", 0),
        "sounds": classes.get("Sound", 0),
        "lights": classes.get("PointLight", 0) + classes.get("SpotLight", 0) + classes.get("SurfaceLight", 0),
        "terrain": classes.get("Terrain", 0),
        "humanoids": classes.get("Humanoid", 0),
        "remotes": len(remotes),
    }
    return {
        "format": "xml-scan",
        "classes": dict(classes.most_common(120)),
        "instancias": int(sum(classes.values())),
        "nomes": nomes[:200],
        "scripts": scripts,
        "protected_strings": source_chars,
        "materiais": dict(materiais.most_common(40)),
        "sistemas": sistemas,
        "modo": "blocos_1mb",
    }


def _extract_pequeno(p: Path, dest: Path | None) -> dict:
    classes: Counter[str] = Counter()
    scripts: list[dict] = []
    remotes: list[dict] = []
    instances = 0
    try:
        for _event, elem in iterparse(p, events=("end",)):
            if elem.tag != "Item" and not (isinstance(elem.tag, str) and elem.tag.endswith("Item")):
                continue
            cls = elem.attrib.get("class", "")
            if not cls:
                continue
            classes[cls] += 1
            instances += 1
            if cls in {"Script", "LocalScript", "ModuleScript"} and len(scripts) < 80:
                src = ""
                for child in list(elem):
                    tag = child.tag if isinstance(child.tag, str) else ""
                    if child.attrib.get("name") == "Source" or "ProtectedString" in tag:
                        src = (child.text or "")[:4000]
                        break
                name = ""
                for child in list(elem):
                    if child.attrib.get("name") == "Name":
                        name = (child.text or "")[:80]
                        break
                if dest is not None and src:
                    rel = Path("scripts") / f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', name or cls)[:40]}_{len(scripts)}.luau"
                    (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                    (dest / rel).write_text(src, encoding="utf-8")
                scripts.append({"name": name or cls, "class": cls, "chars": len(src)})
            if cls.startswith("Remote") or cls.startswith("Bindable"):
                remotes.append({"class": cls})
            elem.clear()
    except Exception as e:  # noqa: BLE001 — XML enorme/quebrado cai no scan
        extra = _scan_blocos(p)
        extra["aviso"] = f"{type(e).__name__}: {e}"
        return extra
    return {
        "format": p.suffix.lower().lstrip("."),
        "classes": dict(classes.most_common(120)),
        "instancias": instances,
        "scripts": scripts,
        "remotes": remotes[:200],
        "sistemas": {
            "parts": classes.get("Part", 0) + classes.get("MeshPart", 0),
            "models": classes.get("Model", 0),
            "scripts": len(scripts),
            "remotes": len(remotes),
        },
        "modo": "iterparse",
    }


def analisar_arquivo(p: Path, dest: Path | None = None) -> dict:
    digest, size = sha_arquivo(p)
    item: dict = {
        "file": str(p),
        "nome": p.name,
        "sha256": digest,
        "bytes": size,
        "mb": round(size / (1024 * 1024), 2),
        "grande": size >= GRANDE,
        "enorme": size >= ENORME,
        "suffix": p.suffix.lower(),
        "quando": datetime.now(timezone.utc).isoformat(),
    }
    suf = p.suffix.lower()
    if suf in XML_EXT or (suf in BIN_EXT and e_xml(p)):
        if size >= GRANDE:
            item.update(_scan_blocos(p))
        else:
            item.update(_extract_pequeno(p, dest))
        item["extractable"] = True
        return item
    if suf in BIN_EXT:
        item.update({
            "format": "roblox-binario",
            "extractable": False,
            "next_step": "converter na VM (rbx-util ou Studio Save As XML) — não fingimos parse de binário",
        })
        return item
    if suf in LUA_EXT:
        raw = p.read_bytes()[:12_000]
        text = raw.decode("utf-8", errors="replace")
        item.update({
            "format": "luau",
            "lines": text.count("\n") + 1,
            "requires": re.findall(r"require\s*\(([^)\n]+)", text)[:40],
            "extractable": True,
        })
        return item
    item.update({"format": suf.lstrip(".") or "outro", "extractable": False})
    return item


def analisar_pasta(source: Path, out: Path, ja_visto: set[str] | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    ja_visto = ja_visto or set()
    exts = XML_EXT | BIN_EXT | LUA_EXT
    if not source.exists():
        manifest = {
            "schema": "arkher-rbxl-knowledge-v3",
            "source": str(source),
            "arquivos_vistos": 0,
            "novos": 0,
            "pulados_hash": 0,
            "gigantes_100mb": 0,
            "projects": [],
            "aviso": "pasta inexistente",
        }
        (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest
    def _rel_ok(p: Path) -> bool:
        try:
            parts = p.relative_to(source).parts
        except ValueError:
            parts = p.parts
        return not any(x in SKIP for x in parts)

    paths = [
        p for p in source.rglob("*")
        if p.is_file() and p.suffix.lower() in exts and _rel_ok(p)
    ]
    projects: list[dict] = []
    pulados = 0
    gigantes = 0
    vistos_nesta = set(ja_visto)
    for p in sorted(paths):
        dest = out / re.sub(r"[^A-Za-z0-9_.-]+", "_", p.stem)[:80]
        item = analisar_arquivo(p, dest if p.stat().st_size < GRANDE else None)
        if item["sha256"] in vistos_nesta:
            pulados += 1
            continue
        vistos_nesta.add(item["sha256"])
        if item.get("enorme"):
            gigantes += 1
        (out / f"{item['sha256'][:16]}.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # amostra de treino compacta — nunca o place de 100 MB
        amostra = (
            f"# jogo {item.get('nome')} sha {item['sha256'][:16]} {item['mb']}MB\n"
            f"# instancias {item.get('instancias', 0)} scripts {item.get('scripts') if isinstance(item.get('scripts'), int) else len(item.get('scripts') or [])}\n"
            f"# classes {list((item.get('classes') or {}).keys())[:40]}\n"
            f"# sistemas {item.get('sistemas')}\n"
        )
        (out / "treino").mkdir(parents=True, exist_ok=True)
        (out / "treino" / f"{item['sha256'][:16]}.txt").write_text(amostra, encoding="utf-8")
        projects.append(item)
    manifest = {
        "schema": "arkher-rbxl-knowledge-v3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "arquivos_vistos": len(paths),
        "novos": len(projects),
        "pulados_hash": pulados,
        "gigantes_100mb": gigantes,
        "projects": [
            {k: pr.get(k) for k in ("file", "nome", "sha256", "bytes", "mb", "grande", "enorme", "format", "instancias", "extractable", "sistemas")}
            for pr in projects
        ],
        "rules": [
            "binario nao e parseado como XML",
            "arquivo >=32MB nao duplica nem carrega arvore",
            "amostra de treino e o grafo, nao o rbxl",
            "hash visto nao reentra",
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
