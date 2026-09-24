"""Gestão de treinamento autorizada pelo servidor.

O treinamento NUNCA roda no navegador. Ele só acontece aqui, quando um usuário
autorizado dispara explicitamente, usando os scripts do próprio projeto.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from backend.app import config
from backend.app.model.training_state import read_state as read_training_state

_LOCK = threading.Lock()
_JOB: dict | None = None

STEPS = {
    "prepare": ["-m", "model.training.prepare_dataset"],
    "validate": ["-m", "model.training.validate_dataset"],
    "tokenizer": ["-m", "model.training.train_tokenizer"],
    "init": ["-m", "model.training.init_weights"],
    "train": ["-m", "model.training.train", "--epochs", "2", "--tag", "web"],
    "evaluate": ["-m", "model.training.evaluate"],
    "report": ["-m", "model.training.report"],
    # Um ciclo seguro pela UI; o serviço 24/7 é iniciado explicitamente pelo
    # operador com model.training.auto_train e pode ser parado por arquivo-stop.
    "auto_train": ["-m", "model.training.auto_train", "--cycles", "1"],
}


def status() -> dict:
    with _LOCK:
        job = dict(_JOB) if _JOB else None
    st = read_training_state()
    return {"job": job, "state": st}


def start(step: str) -> dict:
    global _JOB
    if step not in STEPS:
        raise ValueError(f"Etapa desconhecida: {step}")
    with _LOCK:
        if _JOB and _JOB.get("running"):
            raise RuntimeError("Já existe um trabalho de treinamento em andamento.")
        log_path = config.DATA_DIR / f"training_{step}.log"
        logf = open(log_path, "w", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, *STEPS[step]],
            cwd=str(config.ROOT),
            stdout=logf,
            stderr=subprocess.STDOUT,
            env={**__import__("os").environ, "PYTHONPATH": str(config.ROOT)},
        )
        _JOB = {
            "step": step,
            "pid": proc.pid,
            "running": True,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "log": str(log_path),
        }

    def wait() -> None:
        global _JOB
        code = proc.wait()
        logf.close()
        with _LOCK:
            if _JOB:
                _JOB["running"] = False
                _JOB["exit_code"] = code
                _JOB["finished_at"] = datetime.now(timezone.utc).isoformat()

    threading.Thread(target=wait, daemon=True).start()
    return status()


def tail(step: str, linhas: int = 40) -> list[str]:
    log_path = config.DATA_DIR / f"training_{step}.log"
    if not Path(log_path).exists():
        return []
    return Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()[-linhas:]


def news(limite: int = 20) -> list[dict]:
    """Lista de eventos reais do treino (checkpoints salvos, relatórios).

    Derivada do sistema de arquivos — sem inventar nada. Mais novo primeiro.
    """
    eventos: list[dict] = []
    ckpt_dir = Path(config.MODEL_DIR) / "checkpoints"
    if ckpt_dir.exists():
        for pt in ckpt_dir.glob("*.pt"):
            quando = datetime.fromtimestamp(pt.stat().st_mtime, tz=timezone.utc).isoformat()
            titulo = pt.stem
            detalhe = ""
            try:
                import torch  # import local: só existe no ambiente de treino

                meta = torch.load(pt, map_location="cpu", weights_only=False).get("meta", {})
                val = meta.get("final_val_loss")
                if val is not None:
                    detalhe += f"perda_val={val}"
                if meta.get("steps"):
                    detalhe += f" · passos={meta['steps']}"
                if meta.get("epoch"):
                    detalhe += f" · época={meta['epoch']}"
            except Exception:
                detalhe = detalhe or "metadados indisponíveis"
            eventos.append({"quando": quando, "tipo": "checkpoint", "titulo": titulo, "detalhe": detalhe.strip(" ·")})
    runs_dir = Path(config.MODEL_DIR) / "training" / "runs"
    if runs_dir.exists():
        for md in runs_dir.glob("relatorio-*.md"):
            quando = datetime.fromtimestamp(md.stat().st_mtime, tz=timezone.utc).isoformat()
            eventos.append({"quando": quando, "tipo": "relatorio", "titulo": md.stem, "detalhe": "relatório de avaliação gerado"})
    eventos.sort(key=lambda e: e["quando"], reverse=True)
    return eventos[:limite]
