#!/usr/bin/env python3
"""Treina o tokenizer BPE próprio do ARKHER-1 sobre o corpus preparado."""
from __future__ import annotations

from model.tokenizer.bpe import train
from model.training.common import PREPARED_PATH, VOCAB_PATH, load_model_yaml, log


def main() -> None:
    if not PREPARED_PATH.exists():
        raise SystemExit("corpus ausente; rode antes: python -m model.training.prepare_dataset")
    cfg = load_model_yaml()["model"]["tokenizer"]
    text = PREPARED_PATH.read_text(encoding="utf-8")
    tok = train([text], vocab_size=int(cfg["vocab_size"]), min_frequency=int(cfg.get("min_frequency", 2)))
    tok.save(VOCAB_PATH)
    log(f"tokenizer {cfg['version']} salvo em {VOCAB_PATH} (vocab={len(tok.vocab)}, merges={len(tok.merges)})")


if __name__ == "__main__":
    main()
