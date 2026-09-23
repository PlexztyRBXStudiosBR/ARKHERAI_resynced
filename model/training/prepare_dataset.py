#!/usr/bin/env python3
"""Prepara o dataset: gera dados sintéticos e monta o corpus final.

Estratégia do estágio demo: o conhecimento central autoral é repetido
(peso 8) para que o modelo pequeno o consolide; os dados sintéticos de
aritmética entram uma única vez. Deduplicação acontece apenas DENTRO da
parte sintética; o texto autoral é mantido literalmente.
"""
from __future__ import annotations

import subprocess
import sys

from model.training.common import GENERATED_DIR, PREPARED_PATH, SEED_DIR, log, seed_texts

AUTORAL_REPEAT = 8
EXTERNO_PATH = SEED_DIR.parent / "externos" / "treino_extra.txt"


def main() -> None:
    # 1) garante os dados sintéticos (reproduzíveis)
    subprocess.run([sys.executable, "model/datasets/generate_arithmetic.py"], check=True)

    partes: list[str] = []

    # 2) conteúdo autoral repetido (memorização honesta do núcleo)
    autorais = [t for nome, t in seed_texts() if "generated/" not in nome and nome != "arithmetic.txt"]
    for _ in range(AUTORAL_REPEAT):
        partes.extend(autorais)
    log(f"autoral: {len(autorais)} arquivos x {AUTORAL_REPEAT}")

    # 3) sintético com dedupe interna
    gen_path = SEED_DIR / "generated" / "arithmetic.txt"
    if gen_path.exists():
        seen: set[str] = set()
        linhas: list[str] = []
        for raw in gen_path.read_text(encoding="utf-8").splitlines():
            ln = raw.strip()
            if not ln:
                linhas.append("")
                continue
            key = ln.lower()
            if key in seen:
                continue
            seen.add(key)
            linhas.append(ln)
        partes.append("\n".join(linhas))
        log("sintético: arithmetic.txt (deduplicado)")

    # 4) conhecimento externo licenciado (Wikipédia CC-BY-SA, Gutenberg
    # domínio público etc.) — só entra se existir e com licença registrada
    if EXTERNO_PATH.exists():
        extra = EXTERNO_PATH.read_text(encoding="utf-8").strip()
        if extra:
            partes.append(extra)
            log(f"externo licenciado: treino_extra.txt ({EXTERNO_PATH.stat().st_size} bytes)")

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    PREPARED_PATH.write_text("\n\n".join(partes), encoding="utf-8")
    log(f"corpus pronto: {PREPARED_PATH} ({PREPARED_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
