"""Rate limit simples em memória: janela deslizante de 60 s por usuário+classe."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

_LOCK = threading.Lock()
_HITS: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def check(key_user: str, classe: str, limite_por_minuto: int) -> None:
    now = time.monotonic()
    key = (key_user, classe)
    with _LOCK:
        dq = _HITS[key]
        while dq and now - dq[0] > 60.0:
            dq.popleft()
        if len(dq) >= limite_por_minuto:
            raise HTTPException(
                status_code=429,
                detail={"ok": False, "code": "RATE_LIMITED", "message": "Muitas requisições. Aguarde um instante."},
            )
        dq.append(now)


def reset() -> None:
    with _LOCK:
        _HITS.clear()
