#!/usr/bin/env python3
"""Gera dados sintéticos de aritmética para o dataset semente do ARKHER-1.

Saída 100% sintética e reproduzível (seed fixa). Sem dados externos.
Uso: python model/datasets/generate_arithmetic.py [--out model/datasets/seed/generated/arithmetic.txt]
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

HEADER = "Fatos aritméticos sintéticos gerados pelo projeto ARKHER (sem fontes externas).\n"


def linhas(seed: int = 42) -> list[str]:
    rng = random.Random(seed)
    out: list[str] = []
    # Volume reduzido de propósito: no estágio demo, o conhecimento central
    # (autoral) precisa dominar o corpus; aritmética entra como complemento.
    for _ in range(160):
        a = rng.randint(0, 99)
        b = rng.randint(0, 99)
        out.append(f"PERGUNTA: Quanto é {a} mais {b}?")
        out.append(f"RESPOSTA: {a} mais {b} é {a + b}.")
        out.append("")
    for _ in range(120):
        a = rng.randint(10, 99)
        b = rng.randint(0, a)
        out.append(f"PERGUNTA: Quanto é {a} menos {b}?")
        out.append(f"RESPOSTA: {a} menos {b} é {a - b}.")
        out.append("")
    for _ in range(120):
        a = rng.randint(2, 12)
        b = rng.randint(2, 12)
        out.append(f"PERGUNTA: Quanto é {a} vezes {b}?")
        out.append(f"RESPOSTA: {a} vezes {b} é {a * b}.")
        out.append("")
    for _ in range(60):
        a = rng.randint(0, 50)
        b = rng.randint(0, 50)
        out.append(f"QUESTION: What is {a} plus {b}?")
        out.append(f"ANSWER: {a} plus {b} is {a + b}.")
        out.append("")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="model/datasets/seed/generated/arithmetic.txt")
    args = p.parse_args()
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + "\n".join(linhas()), encoding="utf-8")
    print(f"ok: {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
