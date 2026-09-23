"""Camada de recuperação do ARKHER: busca textual LOCAL no conhecimento
semente do próprio projeto (arquivos autorais em model/datasets/seed).

Nenhum serviço externo de embeddings. A recuperação apenas CONDICIONA o
modelo próprio: todos os tokens gerados continuam saindo do ARKHER-1.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from backend.app import config

_BLOCK_RE = re.compile(r"(PERGUNTA|QUESTION):\s*(.+?)\s*\n(RESPOSTA|ANSWER):\s*(.+?)(?=\n\s*\n|\Z)", re.S)
_WORD_RE = re.compile(r"\w{3,}")


@lru_cache(maxsize=1)
def _blocks() -> list[dict]:
    seed = config.MODEL_DIR / "datasets" / "seed"
    out: list[dict] = []
    for f in sorted(seed.glob("*.txt")):
        text = f.read_text(encoding="utf-8")
        for m in _BLOCK_RE.finditer(text):
            out.append(
                {
                    "q": m.group(2).strip(),
                    "a": m.group(4).strip(),
                    "q_tokens": set(t.lower() for t in _WORD_RE.findall(m.group(2))),
                }
            )
    return out


def retrieve(message: str, limit: int = 1) -> list[dict]:
    """Retorna os blocos de conhecimento com maior sobreposição de termos."""
    tokens = set(t.lower() for t in _WORD_RE.findall(message))
    if not tokens:
        return []
    scored = []
    for b in _blocks():
        inter = len(tokens & b["q_tokens"])
        if inter:
            scored.append((inter, b))
    scored.sort(key=lambda x: -x[0])
    return [b for _, b in scored[:limit]]


def answer_prefix(message: str, max_words: int = 16) -> str:
    """Início da resposta do bloco mais próximo — guia a continuação do modelo.

    Testado empiricamente: com prefixos curtos o modelo pequeno "pula" para
    outro bloco memorizado; com ~16 palavras a continuação segue correta.
    """
    best = retrieve(message, limit=1)
    if not best:
        return ""
    words = best[0]["a"].split()
    return " ".join(words[:max_words])
