"""Filtro de log: remove qualquer coisa parecida com segredo antes de registrar."""
from __future__ import annotations

import logging
import re

_PATTERNS = [
    re.compile(r"ark_[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]{12,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*\S+"),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
]


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        for pat in _PATTERNS:
            msg = pat.sub("[REDACTED]", msg)
        record.msg = msg
        record.args = ()
        return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(isinstance(f, RedactFilter) for f in logger.filters):
        logger.addFilter(RedactFilter())
    return logger
