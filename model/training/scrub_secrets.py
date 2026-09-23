#!/usr/bin/env python3
"""Remove padrões de segredo/dados pessoais de um arquivo de texto.

Uso defensivo: roda antes de incorporar QUALQUER texto novo ao dataset.
Substitui ocorrências por [REMOVIDO].
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PATTERNS = [
    r"(?i)(api[_-]?key|secret|token|passwd|password)\s*[:=]\s*\S+",
    r"sk-[A-Za-z0-9]{16,}",
    r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"(?i)bearer\s+[A-Za-z0-9\-._~+/]{20,}",
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)",
]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("arquivo")
    p.add_argument("--in-place", action="store_true")
    args = p.parse_args()

    path = Path(args.arquivo)
    text = path.read_text(encoding="utf-8")
    total = 0
    for pat in PATTERNS:
        text, n = re.subn(pat, "[REMOVIDO]", text)
        total += n
    if args.in_place:
        path.write_text(text, encoding="utf-8")
        print(f"ok: {total} ocorrências removidas em {path}")
    else:
        sys.stdout.write(text)
        print(f"# {total} ocorrências removidas", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
