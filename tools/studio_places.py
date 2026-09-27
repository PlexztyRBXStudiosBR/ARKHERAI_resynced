#!/usr/bin/env python3
"""Junta todos os .rbxl / .rbxlx numa pasta que o Studio abre como places locais.

Nao publica na nuvem. Nao abre 470 janelas. Hardlink quando da (nao duplica o pack).

  python tools/studio_places.py
  python tools/studio_places.py C:\\Users\\nexus\\ArkherAITraining
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

NEXUS = Path(r"C:\Users\nexus")
EXTS = {".rbxl", ".rbxlx"}
PULAR_DIR = {"pendencias", ".git", "node_modules", "__pycache__"}


def home() -> Path:
    if NEXUS.is_dir():
        return NEXUS
    return Path.home()


def dest_padrao() -> Path:
    return home() / "Documents" / "Roblox" / "ARKHER_Places"


def raizes_padrao() -> list[Path]:
    h = home()
    cand = [
        h / "ArkherAITraining",
        h / "Documents" / "ArkherAITraining",
        h / "Downloads",
        h / "Desktop",
        Path("/storage/emulated/0/ArkherAITraining"),
    ]
    return [p for p in cand if p.is_dir()]


def _pular(p: Path) -> bool:
    return any(part.lower() in PULAR_DIR for part in p.parts)


def achar(raizes: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for root in raizes:
        if not root.exists():
            continue
        if root.is_file():
            it = [root]
        else:
            it = root.rglob("*")
        for p in it:
            if not p.is_file() or _pular(p):
                continue
            if p.suffix.lower() not in EXTS:
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    return out


def _sha(p: Path, limite: int = 2_000_000) -> str:
    h = hashlib.sha256()
    h.update(str(p.stat().st_size).encode())
    with p.open("rb") as f:
        h.update(f.read(limite))
    return h.hexdigest()[:12]


def _nome(p: Path, usado: set[str]) -> str:
    base = p.name
    if base not in usado:
        return base
    stem, ext = p.stem, p.suffix
    alt = f"{stem}_{_sha(p)}{ext}"
    n = 2
    while alt in usado:
        alt = f"{stem}_{_sha(p)}_{n}{ext}"
        n += 1
    return alt


def ligar(src: Path, dst: Path) -> str:
    if dst.exists():
        return "existe"
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
        return "link"
    except OSError:
        shutil.copy2(src, dst)
        return "copia"


def instalar(raizes: list[Path], dest: Path) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    arquivos = achar(raizes)
    usados: set[str] = set()
    itens = []
    for src in arquivos:
        nome = _nome(src, usados)
        usados.add(nome)
        alvo = dest / nome
        modo = ligar(src, alvo)
        itens.append({"de": str(src), "para": str(alvo), "modo": modo})
    lista = dest / "lista.json"
    lista.write_text(json.dumps({"ok": True, "n": len(itens), "dest": str(dest), "itens": itens}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "n": len(itens), "dest": str(dest), "rbxl": sum(1 for i in itens if i["para"].lower().endswith(".rbxl")), "rbxlx": sum(1 for i in itens if i["para"].lower().endswith(".rbxlx"))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("raizes", nargs="*", type=Path)
    ap.add_argument("-d", "--dest", type=Path, default=None)
    a = ap.parse_args()
    raizes = list(a.raizes) if a.raizes else raizes_padrao()
    if not raizes:
        print("nenhuma pasta de pack. Copia o ArkherAITraining do celular para C:\\Users\\nexus\\ArkherAITraining", file=sys.stderr)
        return 2
    dest = a.dest or dest_padrao()
    res = instalar(raizes, dest)
    print(f"{res['n']} places -> {res['dest']}  (rbxl={res['rbxl']} rbxlx={res['rbxlx']})")
    print("No Studio: File > Open from File > essa pasta. Nao abre 470 janelas sozinho.")
    if res["n"] == 0:
        print("0 arquivos. O pack ainda nao esta neste PC.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
