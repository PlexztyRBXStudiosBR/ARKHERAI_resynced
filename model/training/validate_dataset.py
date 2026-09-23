#!/usr/bin/env python3
"""Valida o dataset antes do treino.

Checagens:
1. `dataset.yaml` existe e declara nome, versão, licença e origem.
2. Nenhum segredo aparente (chaves de API, tokens, senhas embutidas).
3. Nenhuma informação pessoal aparente (e-mail, telefone, CPF).
4. Tamanho mínimo/máximo razoável por linha.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

from model.training.common import SEED_DIR, log

SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['\"]?\w{8,}",
    r"sk-[A-Za-z0-9]{16,}",
    r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"(?i)bearer\s+[A-Za-z0-9\-._~+/]{20,}",
    r"AKIA[0-9A-Z]{16}",
]
PII_PATTERNS = [
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",          # e-mail
    r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)",                   # CPF
    r"(?<!\d)\+?\d{2}\s?9?\d{4}-?\d{4}(?!\d)",                   # telefone BR
]


def main() -> int:
    erros: list[str] = []

    meta_path = SEED_DIR / "dataset.yaml"
    if not meta_path.exists():
        erros.append("falta dataset.yaml com licença e origem")
    else:
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        for campo in ("name", "version", "license", "sources"):
            if not meta.get(campo):
                erros.append(f"dataset.yaml sem campo obrigatório: {campo}")

    files = list(SEED_DIR.rglob("*.txt"))
    if not files:
        erros.append("nenhum arquivo .txt no dataset semente")

    n_linhas = 0
    for f in files:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            n_linhas += 1
            for pat in SECRET_PATTERNS:
                if re.search(pat, line):
                    erros.append(f"{f.name}:{i} possível segredo")
            for pat in PII_PATTERNS:
                if re.search(pat, line):
                    erros.append(f"{f.name}:{i} possível dado pessoal")
            if len(line) > 2000:
                erros.append(f"{f.name}:{i} linha longa demais (>2000)")

    if erros:
        for e in erros:
            print(f"FALHOU: {e}")
        return 1
    log(f"dataset válido: {len(files)} arquivos, {n_linhas} linhas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
