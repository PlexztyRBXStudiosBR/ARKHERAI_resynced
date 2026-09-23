#!/usr/bin/env python3
"""Inicializa os pesos do ARKHER-1 e salva um checkpoint não-treinado versionado.

Útil para verificar a arquitetura e começar um treino do zero.
"""
from __future__ import annotations

import torch

from model.architecture.transformer import Arkher1, ArkherConfig
from model.training.common import CHECKPOINT_DIR, dataset_hash, git_commit, load_model_yaml, log, write_state


def main() -> None:
    y = load_model_yaml()
    m = y["model"]
    cfg = ArkherConfig(
        vocab_size=int(m["tokenizer"]["vocab_size"]),
        context_window=int(m["context_window"]),
        n_layers=int(m["n_layers"]),
        n_heads=int(m["n_heads"]),
        d_model=int(m["d_model"]),
        d_ff=int(m["d_ff"]),
        dropout=float(m["dropout"]),
        tie_embeddings=bool(m["tie_embeddings"]),
    )
    model = Arkher1(cfg)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    out = CHECKPOINT_DIR / "arkher1-mini-init.pt"
    torch.save(
        {
            "version": f"{m['version']}-init",
            "quality": "nao_treinado",
            "config": cfg.__dict__,
            "state_dict": model.state_dict(),
            "meta": {"git": git_commit(), "dataset": dataset_hash(), "steps": 0},
        },
        out,
    )
    write_state({"status": "inicializado", "parametros": model.num_parameters(), "arquivo": str(out)})
    log(f"pesos inicializados: {out} ({model.num_parameters():,} parâmetros)")


if __name__ == "__main__":
    main()
