#!/usr/bin/env python3
"""DsOS — tela real + toque. Sem desktop HTML falso, sem IA de terceiro.

No desenho original: 8765 = agente, 8766 = DsOS. Dois prints ao mesmo tempo
travam o Windows. Aqui o núcleo de tela/toque JÁ ESTÁ no agent.py (8765).

Este arquivo só sobe o mesmo processo na porta 8766 se você quiser o desenho
antigo. NÃO rode agent.py e dsos_core.py juntos.

  ARKHER_AGENT_TOKEN=agt_… python workers/workspace/dsos_core.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("ARKHER_AGENT_PORT", os.environ.get("DSOS_PORT", "8766"))

# mesmo diretório do agent.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(agent.main())
