"""Sessão Windows do produto: sempre a usuária nexus, nunca runneradmin."""
from __future__ import annotations

import os
from pathlib import Path

NEXUS = "nexus"
NEXUS_HOME = Path(r"C:\Users\nexus")
_ACOES = {"runneradmin", "runnervm99s1a", "system", "local service", "network service"}


def usuario_sessao() -> str:
    forced = (os.environ.get("ARKHER_WIN_USER") or "").strip()
    if forced and forced.lower() not in _ACOES:
        return forced[:80]
    env = (os.environ.get("USERNAME") or os.environ.get("USER") or "").strip()
    if env.lower() in _ACOES or not env:
        return NEXUS
    if NEXUS_HOME.is_dir():
        return NEXUS
    if env.lower() == NEXUS:
        return NEXUS
    return NEXUS


def home_sessao() -> Path:
    forced = os.environ.get("ARKHER_WIN_HOME") or os.environ.get("ARKHER_STATE")
    if forced:
        p = Path(forced)
        if p.name == "arkher_state":
            p = p.parent
        if p.is_dir():
            return p
    if NEXUS_HOME.is_dir():
        return NEXUS_HOME
    return Path.home()


def estado_dir() -> Path:
    env = os.environ.get("ARKHER_STATE")
    if env:
        return Path(env)
    return home_sessao() / "arkher_state"
