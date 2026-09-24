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

## Sempre ligado (auto-ligar + auto-recuperar)

A alternativa legítima para "não precisar ficar ligando a máquina/serviço":
o ARKHER se mantém no ar sozinho, **na sua própria máquina** — sem painel
remoto, sem controle de tela, sem tocar em outros computadores.

| Modo | O que mantém ligado |
|---|---|
| Docker | `restart: unless-stopped` + `healthcheck` no `docker-compose.yml` (sobrevive a boot e a travamento) |
| Linux (systemd) | `deploy/arkher.service` com `Restart=always` + `enable` no boot: `sudo cp deploy/arkher.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now arkher` |
| Camada extra | `deploy/arkher-watchdog.sh` checa `/api/health` a cada 2 min (cron) e religa se não responder |
| Logs | `journalctl -u arkher -f` ou `docker compose logs -f` |

Com isso, a máquina liga uma vez (ou nem precisa de login) e o serviço volta
sozinho de qualquer queda. A interface mostra o estado real em tempo real na
barra de status — nada de "ligar de novo pelo app".

> Fora do produto por decisão: ver/controlar tela de VM remotamente pelo app,
> religar máquinas por automação de CI e shell aberto. Motivo: viola termos de
> serviço das plataformas (risco de ban) e abre superfície de ataque.

## Conector Blender (geração 3D real)

Com o Blender instalado na máquina do backend, a ARKHER **executa de verdade**:
o comando `/blender terreno|cena|personagem [seed]` roda o script em modo
headless e devolve `.glb` + render `.png` num zip. Sem Blender no servidor, o
mesmo comando entrega o script `.py` pronto para rodar na máquina do usuário.

- Binário detectado automaticamente (`blender` no PATH) ou via `ARKHER_BLENDER=/caminho/blender`.
- No Docker: adicione o Blender à imagem ou monte o binário; o resto é automático.

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
