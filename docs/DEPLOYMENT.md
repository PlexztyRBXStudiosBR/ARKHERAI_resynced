# Deploy honesto do ARKHER AI

Arquitetura real:

```
Navegador → frontend ARKHER (estático) → backend próprio → modelo próprio
```

Se o frontend for servido por uma CDN estática (ex.: Vercel/Netlify), **o modelo não
está rodando lá** — ele roda no backend. Aponte o frontend para o backend por
variável e mostre erro claro se ele estiver offline (a interface já faz isso).

## Docker (recomendado)

```bash
docker compose up --build
# health check
curl http://localhost:8710/api/health
```

## Manual

```bash
cd frontend && npm install && npm run build && cd ..
PYTHONPATH=. .venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8710
```

O backend serve `frontend/dist` automaticamente quando `ARKHER_SERVE_FRONTEND=1`.

## Checklist de produção
- [ ] `ARKHER_CORS_ORIGINS` restrito às suas origens reais
- [ ] volume persistente para `ARKHER_DATA_DIR`
- [ ] timeout/limite de corpo no proxy reverso (SSE: desligar buffering — o backend
      já envia `X-Accel-Buffering: no`)
- [ ] monitorar `GET /api/health` e `GET /api/model/status`
- [ ] backups do volume (conversas, memórias, uploads)

## O que NÃO fazer
- Prometer que "o modelo roda na Vercel/CDN" se só o frontend está lá.
- Apontar o frontend para qualquer API de IA de terceiros "enquanto o modelo não sai".
- Deixar o site em carregamento infinito: o frontend tem timeout e estados de erro.
