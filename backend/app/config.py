"""Configuração do backend ARKHER AI.

Todo valor sensível vem de variável de ambiente com padrão seguro.
Nenhum segredo vive neste arquivo nem no frontend.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

VERSION = "0.1.0"
MODEL_NAME = "ARKHER-1 mini"

DATA_DIR = Path(os.environ.get("ARKHER_DATA_DIR", str(ROOT / "data")))
MODEL_DIR = ROOT / "model"
CHECKPOINT_PATH = Path(os.environ.get("ARKHER_CHECKPOINT", str(MODEL_DIR / "checkpoints" / "latest.pt")))
TOKENIZER_PATH = Path(os.environ.get("ARKHER_TOKENIZER", str(MODEL_DIR / "tokenizer" / "vocab" / "bpe_v1.json")))

HOST = os.environ.get("ARKHER_HOST", "0.0.0.0")
PORT = int(os.environ.get("ARKHER_PORT", "8710"))

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "ARKHER_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

# Limites de entrada/saída
MAX_MESSAGE_CHARS = int(os.environ.get("ARKHER_MAX_MESSAGE_CHARS", "4000"))
MAX_INPUT_TOKENS = int(os.environ.get("ARKHER_MAX_INPUT_TOKENS", "140"))
MAX_NEW_TOKENS = int(os.environ.get("ARKHER_MAX_NEW_TOKENS", "224"))
GEN_TIMEOUT_S = float(os.environ.get("ARKHER_GEN_TIMEOUT_S", "120"))
MODEL_LOAD_TIMEOUT_S = float(os.environ.get("ARKHER_MODEL_LOAD_TIMEOUT_S", "90"))

# Rate limit (janela de 1 minuto)
RATE_CHAT_PER_MIN = int(os.environ.get("ARKHER_RATE_CHAT_PER_MIN", "30"))
RATE_API_PER_MIN = int(os.environ.get("ARKHER_RATE_API_PER_MIN", "240"))

# Histórico enviado ao modelo
HISTORY_TURNS = int(os.environ.get("ARKHER_HISTORY_TURNS", "8"))

SERVE_FRONTEND = os.environ.get("ARKHER_SERVE_FRONTEND", "1") == "1"
FRONTEND_DIST = ROOT / "frontend" / "dist"

SYSTEM_PROMPT = """Você é a ARKHER AI, uma inteligência artificial própria executada pelo backend autorizado do projeto ARKHER.

Responda o que o usuário pedir.
Se não souber, diga que não sabe. Não invente fatos, resultados, fontes ou ações não executadas.
Não diga que consultou a internet, rodou código, leu arquivos ou alterou uma máquina se isso não aconteceu de verdade.

Ferramentas só podem ser usadas quando o backend autorizar a ferramenta, validar os argumentos e registrar a ação.
Ações destrutivas, publicação, envio de dados, execução de comandos e acesso a recursos externos exigem confirmação explícita.

Você é a IA do ARKHER. Não atribua sua resposta a outro provedor ou modelo.
Se o modelo próprio estiver indisponível, informe isso claramente em vez de inventar uma resposta."""
