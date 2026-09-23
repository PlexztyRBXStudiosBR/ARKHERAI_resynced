"""Leitura do estado de treinamento gravado pelos scripts do modelo."""
from __future__ import annotations

import json
from pathlib import Path

from backend.app import config


def read_state() -> dict:
    path = Path(config.MODEL_DIR) / "checkpoints" / "training_state.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"status": "estado_corrompido"}
    return {"status": "nunca_executado"}
