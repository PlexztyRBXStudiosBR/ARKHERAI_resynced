#!/usr/bin/env python3
"""Nó de treinamento ARKHER para Lightning AI Studios (ou qualquer Linux com GPU).

Uso no Studio (créditos gratuitos de GPU):
  git clone <este repositório> && cd ARKHER_resynced
  pip install torch pyyaml
  PYTHONPATH=. python workers/lightning/treino.py --epochs 10

O script retoma de model/checkpoints/latest.pt quando existe, treina, avalia e
deixa o checkpoint novo pronto para voltar ao repositório (ou ao depósito privado
via workers/sync/hf_sync.py push).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> None:
    print(f"[no] $ {' '.join(cmd)}", flush=True)
    subprocess.run([sys.executable, *cmd], cwd=ROOT, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--tag", type=str, default="rede")
    args = ap.parse_args()

    ckpt = ROOT / "model" / "checkpoints" / "latest.pt"
    run(["-m", "model.training.prepare_dataset"])
    run(["-m", "model.training.validate_dataset"])
    if not (ROOT / "model" / "tokenizer" / "vocab" / "bpe_v1.json").exists():
        run(["-m", "model.training.train_tokenizer"])

    train_cmd = ["-m", "model.training.train", "--epochs", str(args.epochs), "--tag", args.tag]
    if ckpt.is_file():
        train_cmd += ["--resume", str(ckpt)]
    run(train_cmd)

    run(["-m", "model.training.evaluate"])
    run(["-m", "model.training.report"])
    print("[no] treino concluído. Devolva model/checkpoints/latest.pt ao repositório")
    print("     (git commit) ou use: python workers/sync/hf_sync.py push")


if __name__ == "__main__":
    main()
