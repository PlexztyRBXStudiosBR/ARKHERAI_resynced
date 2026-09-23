"""Runtime do modelo próprio ARKHER-1.

Estados honestos:
  model_not_installed — nenhum checkpoint local encontrado;
  model_loading       — carregamento em andamento (com timeout);
  ready               — modelo próprio em memória;
  error               — falha real, com mensagem visível.

Nunca simula resposta nem usa serviço externo.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from backend.app import config

# RLock: status() pode ser chamado dentro de load() (mesma thread).
_LOCK = threading.RLock()
_STATE = "model_not_installed"
_ERROR: str | None = None
_ENGINE = None
_LOAD_THREAD: threading.Thread | None = None


def _checkpoint_exists() -> bool:
    return Path(config.CHECKPOINT_PATH).is_file() and Path(config.TOKENIZER_PATH).is_file()


def status() -> dict:
    with _LOCK:
        state = _STATE
        err = _ERROR
        engine = _ENGINE
    base = {
        "name": config.MODEL_NAME,
        "state": state,
        "checkpoint_present": _checkpoint_exists(),
        "checkpoint_path": str(config.CHECKPOINT_PATH),
    }
    if state == "ready" and engine is not None:
        info = engine.info
        base.update(
            {
                "checkpoint_version": info.checkpoint_version,
                "device": info.device,
                "parameters": info.num_parameters,
                "context_window": info.context_window,
                "vocab_size": info.vocab_size,
                "quality": info.quality,
            }
        )
    if err:
        base["error"] = err
    return base


def _do_load() -> None:
    global _STATE, _ERROR, _ENGINE
    try:
        root = str(config.ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)
        from model.inference.engine import InferenceEngine  # import tardio: torch é pesado

        engine = InferenceEngine(config.TOKENIZER_PATH, config.CHECKPOINT_PATH)
        with _LOCK:
            _ENGINE = engine
            _STATE = "ready"
            _ERROR = None
    except Exception as e:  # falha real, reportada com clareza
        with _LOCK:
            _STATE = "error"
            _ERROR = f"{type(e).__name__}: {e}"


def load(wait_seconds: float | None = None) -> dict:
    """Dispara o carregamento (idempotente). Opcionalmente espera até N segundos."""
    global _STATE, _ERROR, _LOAD_THREAD
    with _LOCK:
        if _STATE in ("ready", "model_loading"):
            pass
        elif not _checkpoint_exists():
            _STATE = "model_not_installed"
            return status()
        else:
            _STATE = "model_loading"
            _ERROR = None
            _LOAD_THREAD = threading.Thread(target=_do_load, name="arkher-model-load", daemon=True)
            _LOAD_THREAD.start()

    if wait_seconds is not None:
        thread = _LOAD_THREAD
        if thread is not None:
            thread.join(timeout=wait_seconds)
    return status()


def ensure_loaded() -> None:
    """Chamado no boot: se há checkpoint, carrega sem bloquear o servidor."""
    if _checkpoint_exists():
        load(wait_seconds=None)


def engine_or_none():
    with _LOCK:
        return _ENGINE if _STATE == "ready" else None


def generate(prompt_text: str, max_new_tokens: int, stop_event: threading.Event, timeout_s: float, temperature: float = 0.0):
    """Gera tokens a partir do texto. Retorna gerador de strings (delta de texto).

    Erros viram exceção RuntimeError com código honesto.
    """
    engine = engine_or_none()
    if engine is None:
        st = status()
        if st["state"] == "model_not_installed":
            raise RuntimeError("MODEL_NOT_INSTALLED")
        if st["state"] == "model_loading":
            raise RuntimeError("MODEL_LOADING")
        raise RuntimeError("MODEL_ERROR")

    ids = engine.encode(prompt_text)
    if len(ids) > config.MAX_INPUT_TOKENS:
        ids = ids[-config.MAX_INPUT_TOKENS:]
    deadline = time.monotonic() + timeout_s
    produced = engine.decode([])
    seq: list[int] = []
    for tok_id in engine.generate(
        ids,
        max_new_tokens=max_new_tokens,
        stop_event=stop_event,
        deadline=deadline,
        temperature=temperature,
    ):
        seq.append(tok_id)
        new_full = engine.decode(seq)
        delta = new_full[len(produced):]
        produced = new_full
        if delta:
            yield delta
