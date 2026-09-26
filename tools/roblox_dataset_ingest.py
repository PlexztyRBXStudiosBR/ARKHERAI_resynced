#!/usr/bin/env python3
"""Organiza e converte o acervo Roblox no celular.

Uso no Termux:
  python tools/roblox_dataset_ingest.py
  python tools/roblox_dataset_ingest.py /storage/emulated/0/ArkherAITraining --once

XML fica em:
  _arkher/xml/rbxlx/<categoria>/
  _arkher/xml/rbxmx/<categoria>/
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.acervo.convert import DEFAULT_ROOT, ingerir  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=60)
    a = ap.parse_args()
    while True:
        res = ingerir(a.root)
        n = len(res.get("arquivos") or [])
        print(
            f"[arkher-ingest] ok={res.get('ok')} arquivos={n} "
            f"rbxlx={res.get('xml_rbxlx', 0)} rbxmx={res.get('xml_rbxmx', 0)} "
            f"pendencias={res.get('pendencias', 0)}",
            flush=True,
        )
        if a.once:
            return 0 if res.get("ok") else 1
        time.sleep(max(5, a.interval))


if __name__ == "__main__":
    raise SystemExit(main())
