#!/usr/bin/env bash
# ARKHER AI — vigia de saude (watchdog). Verifica /api/health e religa o servico
# se ele nao responder. Uso legitimo: mantem o proprio servico no ar, sem nunca
# controlar outras maquinas.
#
# Modo Docker:    HEALTHCHECK do Dockerfile + restart: unless-stopped ja cuidam.
# Modo systemd:   Restart=always ja cuida; este vigia e uma camada extra.
# Modo manual:    agende com cron:
#   */2 * * * * /caminho/ARKHERAI_resynced/deploy/arkher-watchdog.sh >> /var/log/arkher-watchdog.log 2>&1

set -u
URL="${ARKHER_URL:-http://127.0.0.1:8710/api/health}"

if curl -sf -m 8 "$URL" >/dev/null 2>&1; then
  echo "$(date -Is) OK: ARKHER respondendo."
  exit 0
fi

echo "$(date -Is) FALHA: sem resposta em $URL — religando."
if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q '^arkher\.service'; then
  sudo systemctl restart arkher
elif command -v docker >/dev/null 2>&1 && docker compose ps >/dev/null 2>&1; then
  docker compose restart
else
  echo "$(date -Is) AVISO: nenhum mecanismo de religamento encontrado (systemd/docker)."
  exit 1
fi
