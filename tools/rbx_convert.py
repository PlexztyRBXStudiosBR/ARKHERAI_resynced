#!/usr/bin/env python3
"""Conversor ARKHER: .rbxl → .rbxlx  e  .rbxm → .rbxmx

Uso:
  python tools/rbx_convert.py mapa.rbxl
  python tools/rbx_convert.py modelo.rbxm -o saida.rbxmx
  python tools/rbx_convert.py pasta/ --recursivo
  python tools/rbx_convert.py a.rbxl b.rbxm c.rbxlx

XML já existente é copiado. Binário vira XML de verdade (não renomeia).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.acervo.rbx_binary import ConvertError, convert_file, convert_many  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="rbxl/rbxm → rbxlx/rbxmx")
    ap.add_argument("entradas", nargs="+", type=Path)
    ap.add_argument("-o", "--saida", type=Path, help="só vale com um arquivo")
    ap.add_argument("--recursivo", action="store_true")
    a = ap.parse_args()
    if a.saida is not None:
        if len(a.entradas) != 1 or not a.entradas[0].is_file():
            print(" -o só com um arquivo", file=sys.stderr)
            return 2
        try:
            d = convert_file(a.entradas[0], a.saida)
        except ConvertError as e:
            print(f"falhou: {e}", file=sys.stderr)
            return 1
        print(f"ok {a.entradas[0]} -> {d}")
        return 0
    rows = convert_many(a.entradas, recursive=a.recursivo)
    if not rows:
        print("nenhum .rbxl/.rbxm/.rbxlx/.rbxmx", file=sys.stderr)
        return 2
    n_ok = 0
    for r in rows:
        if r["ok"]:
            n_ok += 1
            print(f"ok  {r['arquivo']} -> {r['saida']}")
        else:
            print(f"nao {r['arquivo']}  {r['erro']}", file=sys.stderr)
    print(f"{n_ok}/{len(rows)} convertidos")
    return 0 if n_ok == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
