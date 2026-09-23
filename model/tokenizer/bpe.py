"""Tokenizer BPE próprio do ARKHER-1.

Implementado do zero para o projeto: nenhum componente externo de tokenizer.
- Treina merges de pares de bytes/characters sobre um corpus.
- Salva vocabulário versionado em JSON ({version, vocab, merges}).
- API: train(), encode(text) -> list[int], decode(ids) -> str.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

SPECIAL_TOKENS = ["<pad>", "<unk>", "<bos>", "<eos>", "<sep>"]
TOKENIZER_VERSION = "bpe_v1"


def apply_merge(seq: list[str], pair: tuple[str, str], merged: str) -> list[str]:
    """Aplica um merge de par a uma sequência de pedaços."""
    out: list[str] = []
    i = 0
    while i < len(seq):
        if i < len(seq) - 1 and seq[i] == pair[0] and seq[i + 1] == pair[1]:
            out.append(merged)
            i += 2
        else:
            out.append(seq[i])
            i += 1
    return out


class BpeTokenizer:
    def __init__(self, vocab: dict[str, int], merges: list[tuple[str, str]]):
        self.vocab = vocab
        self.id2tok = {i: t for t, i in vocab.items()}
        self.merges = merges
        self.merge_rank = {pair: i for i, pair in enumerate(merges)}
        self.pad_id = vocab["<pad>"]
        self.unk_id = vocab["<unk>"]
        self.bos_id = vocab["<bos>"]
        self.eos_id = vocab["<eos>"]
        self.sep_id = vocab["<sep>"]

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _words(text: str) -> list[str]:
        # Mantém blocos de letras/números e pontuação como tokens separados.
        return re.findall(r"[A-Za-zÀ-ÿ0-9]+|[^\sA-Za-zÀ-ÿ0-9]|\s+", text)

    @staticmethod
    def _pairs(seq: list[str]) -> set[tuple[str, str]]:
        return {(seq[i], seq[i + 1]) for i in range(len(seq) - 1)}

    # ------------------------------------------------------------------- api
    def encode(self, text: str, add_bos: bool = False, add_eos: bool = False) -> list[int]:
        ids: list[int] = []
        if add_bos:
            ids.append(self.bos_id)
        for word in self._words(text):
            seq = list(word)
            while True:
                pairs = self._pairs(seq)
                if not pairs:
                    break
                best = min(
                    (self.merge_rank[p] for p in pairs if p in self.merge_rank),
                    default=None,
                )
                if best is None:
                    break
                pair = self.merges[best]
                seq = apply_merge(seq, pair, pair[0] + pair[1])
            ids.extend(self.vocab.get(t, self.unk_id) for t in seq)
        if add_eos:
            ids.append(self.eos_id)
        return ids

    def decode(self, ids: Iterable[int], skip_special: bool = True) -> str:
        toks = []
        for i in ids:
            t = self.id2tok.get(int(i))
            if t is None:
                continue
            if skip_special and t in SPECIAL_TOKENS:
                continue
            toks.append(t)
        return "".join(toks)

    # ------------------------------------------------------------------ save
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"version": TOKENIZER_VERSION, "vocab": self.vocab, "merges": self.merges},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def load(path: Path) -> "BpeTokenizer":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return BpeTokenizer(data["vocab"], [tuple(m) for m in data["merges"]])


def train(texts: Iterable[str], vocab_size: int, min_frequency: int = 2) -> BpeTokenizer:
    """Treina um BPE simples sobre `texts` até atingir vocab_size."""
    freq: Counter[tuple[str, str]] = Counter()
    corpus_words: Counter[str] = Counter()
    for text in texts:
        for w in BpeTokenizer._words(text):
            corpus_words[w] += 1

    # palavras pré-tokenizadas em caracteres, ponderadas por frequência
    word_seqs: dict[str, list[str]] = {w: list(w) for w in corpus_words}
    vocab: dict[str, int] = {t: i for i, t in enumerate(SPECIAL_TOKENS)}
    # símbolos base (caracteres)
    chars = sorted({c for w in corpus_words for c in w})
    for c in chars:
        if c not in vocab:
            vocab[c] = len(vocab)

    merges: list[tuple[str, str]] = []

    def recount() -> None:
        freq.clear()
        for w, count in corpus_words.items():
            seq = word_seqs[w]
            for i in range(len(seq) - 1):
                freq[(seq[i], seq[i + 1])] += count

    recount()
    while len(vocab) < vocab_size and freq:
        pair, count = max(freq.items(), key=lambda kv: (kv[1], -len(kv[0][0])))
        if count < min_frequency:
            break
        merged = pair[0] + pair[1]
        merges.append(pair)
        vocab[merged] = len(vocab)
        for w in corpus_words:
            word_seqs[w] = apply_merge(word_seqs[w], pair, merged)
        recount()

    return BpeTokenizer(vocab, merges)
