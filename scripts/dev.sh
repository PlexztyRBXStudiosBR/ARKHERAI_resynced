#!/usr/bin/env bash
# Desenvolvimento local do ARKHER AI:
# - backend em :8710 (servindo o build do frontend, se existir)
# - frontend em :5173 com proxy /api -> :8710 (opcional, para hot-reload)
set -e
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r backend/requirements.txt
  .venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
fi

export PYTHONPATH="$PWD"
.venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port "${ARKHER_PORT:-8710}" --reload
