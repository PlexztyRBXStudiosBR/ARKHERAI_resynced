#!/usr/bin/env python3
"""Exporta relatório de treinamento em Markdown (versão de dados e código incluídas)."""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import torch

from model.training.common import CHECKPOINT_DIR, ROOT, dataset_hash, git_commit, log, read_state


def main() -> None:
    state = read_state()
    ckpt_path = Path(state.get("checkpoint", CHECKPOINT_DIR / "latest.pt"))
    meta: dict = {}
    if ckpt_path.exists():
        payload = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        meta = payload.get("meta", {})

    runs_dir = ROOT / "model" / "training" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    out = runs_dir / f"relatorio-{datetime.datetime.now():%Y%m%d-%H%M%S}.md"
    linhas = [
        "# Relatório de treinamento — ARKHER-1",
        "",
        f"- Data: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
        f"- Código (git): `{git_commit()}`",
        f"- Hash do dataset preparado: `{dataset_hash()}`",
        f"- Checkpoint: `{ckpt_path.name if ckpt_path.exists() else 'inexistente'}`",
        f"- Versão do checkpoint: `{meta.get('git', 'n/d')}` passos={meta.get('steps', 'n/d')}",
        f"- Perda final (treino): {meta.get('final_train_loss', 'n/d')}",
        f"- Perda final (validação): {meta.get('final_val_loss', 'n/d')}",
        "",
        "## Estado da última execução",
        "",
        "```json",
        json.dumps(state, ensure_ascii=False, indent=1),
        "```",
        "",
        "## Honestidade",
        "",
        "Modelo pequeno treinado em CPU no dataset semente do projeto.",
        "Estado de qualidade: experimental. Não é conversacional até que haja",
        "dados e hardware suficientes — ver docs/TRAINING.md e docs/HARDWARE.md.",
        "",
    ]
    out.write_text("\n".join(linhas), encoding="utf-8")
    log(f"relatório: {out}")


if __name__ == "__main__":
    main()
