#!/usr/bin/env python3
"""CLI: extrai conhecimento do pack Roblox (rbxlx/rbxmx/lua; binário fica pendente)."""
from __future__ import annotations

import argparse
from pathlib import Path

from backend.app.acervo.analise import analisar_pasta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("--out", type=Path, default=Path("model/datasets/generated/rbxl_knowledge"))
    a = ap.parse_args()
    man = analisar_pasta(a.source, a.out)
    print(
        f"[rbxl] vistos={man.get('arquivos_vistos')} novos={man.get('novos')} "
        f"pulados={man.get('pulados_hash')} gigantes={man.get('gigantes_100mb')} → {a.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
