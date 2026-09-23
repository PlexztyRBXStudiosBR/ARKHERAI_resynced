"""Utilitários compartilhados pelos scripts de treinamento do ARKHER-1."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "model"
SEED_DIR = MODEL_DIR / "datasets" / "seed"
GENERATED_DIR = MODEL_DIR / "datasets" / "generated"
PREPARED_PATH = GENERATED_DIR / "train.txt"
STATE_PATH = MODEL_DIR / "checkpoints" / "training_state.json"
VOCAB_PATH = MODEL_DIR / "tokenizer" / "vocab" / "bpe_v1.json"
CHECKPOINT_DIR = MODEL_DIR / "checkpoints"


def load_model_yaml() -> dict:
    return yaml.safe_load((MODEL_DIR / "config.yaml").read_text(encoding="utf-8"))


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or "sem-git"
    except Exception:
        return "sem-git"


def dataset_hash() -> str:
    import hashlib

    h = hashlib.sha256()
    if PREPARED_PATH.exists():
        h.update(PREPARED_PATH.read_bytes())
    return h.hexdigest()[:16]


def write_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE_PATH)


def read_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"status": "nunca_executado"}


def seed_texts() -> list[tuple[str, str]]:
    """Retorna [(nome_arquivo, texto)] dos arquivos do dataset semente (recursivo)."""
    out = []
    for f in sorted(SEED_DIR.rglob("*.txt")):
        out.append((str(f.relative_to(SEED_DIR)), f.read_text(encoding="utf-8")))
    gen = GENERATED_DIR / "arithmetic.txt"
    if gen.exists():
        out.append((gen.name, gen.read_text(encoding="utf-8")))
    return out


def log(msg: str) -> None:
    print(f"[treino] {msg}", flush=True)
