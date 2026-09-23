#!/usr/bin/env python3
"""Sincronização de checkpoint do ARKHER-1 com um depósito PRIVADO do dono do projeto.

Uso (o token vem do ambiente/secrets do Kaggle ou Colab — nunca commitado):

  export ARKHER_SYNC_TOKEN=hf_xxx        # token de escrita do SEU usuário
  export ARKHER_SYNC_REPO=usuario/arkher-pesos   # repo privado que você criou
  python workers/sync/hf_sync.py pull     # baixa latest.pt para model/checkpoints/
  python workers/sync/hf_sync.py push     # envia model/checkpoints/latest.pt

Requisito: pip install huggingface_hub
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CKPT = ROOT / "model" / "checkpoints" / "latest.pt"


def _client():
    token = os.environ.get("ARKHER_SYNC_TOKEN", "")
    repo = os.environ.get("ARKHER_SYNC_REPO", "")
    if not token or not repo:
        raise SystemExit(
            "Defina ARKHER_SYNC_TOKEN e ARKHER_SYNC_REPO (segredos do Kaggle/Colab). "
            "Nunca escreva o token no código."
        )
    from huggingface_hub import HfApi

    return HfApi(token=token), repo


def pull() -> None:
    api, repo = _client()
    CKPT.parent.mkdir(parents=True, exist_ok=True)
    path = api.hf_hub_download(repo_id=repo, filename="latest.pt")
    CKPT.write_bytes(Path(path).read_bytes())
    print(f"ok: checkpoint baixado para {CKPT} ({CKPT.stat().st_size} bytes)")


def push() -> None:
    api, repo = _client()
    if not CKPT.is_file():
        raise SystemExit(f"nada para enviar: {CKPT} não existe")
    api.upload_file(path_or_fileobj=str(CKPT), path_in_repo="latest.pt", repo_id=repo)
    state = ROOT / "model" / "checkpoints" / "training_state.json"
    if state.is_file():
        api.upload_file(path_or_fileobj=str(state), path_in_repo="training_state.json", repo_id=repo)
    print(f"ok: {CKPT.name} enviado para {repo} (repo privado)")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("pull", "push"):
        raise SystemExit("uso: hf_sync.py [pull|push]")
    pull() if sys.argv[1] == "pull" else push()


if __name__ == "__main__":
    main()
