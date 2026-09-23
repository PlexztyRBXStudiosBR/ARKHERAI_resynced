#!/usr/bin/env python3
"""Avalia um checkpoint do ARKHER-1: perda e perplexidade em holdout."""
from __future__ import annotations

import argparse
import math

import torch

from model.architecture.transformer import Arkher1, ArkherConfig
from model.tokenizer.bpe import BpeTokenizer
from model.training.common import PREPARED_PATH, VOCAB_PATH, log
from model.training.train import build_sequences


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default="model/checkpoints/latest.pt")
    args = ap.parse_args()

    payload = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    cfg = ArkherConfig.from_dict(payload["config"])
    model = Arkher1(cfg)
    model.load_state_dict(payload["state_dict"])
    model.eval()

    tok = BpeTokenizer.load(VOCAB_PATH)
    ids = tok.encode(PREPARED_PATH.read_text(encoding="utf-8"))
    data = build_sequences(ids, cfg.context_window)
    val = data[torch.randperm(len(data))[: max(8, len(data) // 10)]]

    total = 0.0
    n = 0
    bs = 16
    with torch.no_grad():
        for b in range(0, len(val), bs):
            batch = val[b : b + bs]
            _, loss = model(batch[:, 0, :], batch[:, 1, :])
            total += float(loss.item())
            n += 1
    loss = total / max(1, n)
    log(f"checkpoint={payload['version']} perda_val={loss:.4f} perplexidade={math.exp(min(20, loss)):.2f}")


if __name__ == "__main__":
    main()
