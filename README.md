# ARKHER AI

> **ARKHER AI — sua inteligência, seu contexto, seu controle.**

A ARKHER é uma inteligência artificial **própria do projeto**: frontend, backend,
modelo, tokenizer, memória e ferramentas pertencem ao ARKHER. O navegador conversa
**somente** com o backend oficial; não existe chamada a provedor de IA externo,
fallback silencioso ou resposta simulada.

Especialidade: **game dev, engines, código e tecnologia** — sem impedir outros assuntos.

---

## Estado real (leia antes de usar)

| Peça | Estado |
| --- | --- |
| Interface (chat, memória, ferramentas, treino, config) | ✅ pronta e testada |
| Backend próprio (API, auth, SSE, segurança) | ✅ pronto e testado |
| Modelo próprio **ARKHER-1 mini** | ✅ instalado (checkpoint `v0.1.0-gamedev`) |
| Qualidade do modelo | ⚠️ **experimental** — 3,98 M de parâmetros treinados em CPU num corpus semente de ~89 mil tokens, com foco em game dev. Responde bem os temas do corpus (3D, animação, Roblox, engines, netcode, identidade); fora disso, é limitada. |
| Infraestrutura de treinamento | ✅ real e reproduzível (tokenizer próprio, treino com retomada, avaliação, relatório) |
| Camada extra de segurança/correção de resposta | ✅ ativa (recusas, verificação aritmética, alegações de ações, redação de logs) |

**Nunca declaramos "IA própria pronta" além disso.** Um modelo conversacional amplo
exige dados e hardware documentados em `docs/HARDWARE.md`.

---

## Rodar localmente

```bash
# 1. backend (Python 3.11+)
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
PYTHONPATH=. .venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8710

# 2. frontend (Node 22+) — desenvolvimento com hot-reload
cd frontend && npm install && npm run dev     # http://localhost:5173

# ou build de produção servido pelo próprio backend
cd frontend && npm run build                  # backend passa a servir frontend/dist
```

O backend mostra o estado real no log: `Modelo: ready | model_not_installed | model_loading | error`.

## Docker

```bash
docker compose up --build     # http://localhost:8710
```

## Testes

```bash
.venv/bin/python -m pytest backend/tests -q      # 24 testes de backend
cd frontend && npx vitest run                     # 16 testes de frontend
bash scripts/integration_check.sh                 # 17 verificações contra o servidor vivo
```

## Treinamento (o pipeline completo)

```bash
PYTHONPATH=. .venv/bin/python -m model.training.prepare_dataset   # dados sintéticos + corpus
PYTHONPATH=. .venv/bin/python -m model.training.validate_dataset  # licença/segredos/PII
PYTHONPATH=. .venv/bin/python -m model.training.train_tokenizer   # BPE próprio
PYTHONPATH=. .venv/bin/python -m model.training.train --epochs 8  # treino com checkpoint
PYTHONPATH=. .venv/bin/python -m model.training.evaluate          # perda/perplexidade
PYTHONPATH=. .venv/bin/python -m model.training.report            # relatório versionado
```

Ou use a aba **Treino** do site (roda no servidor, nunca no navegador, com confirmação).

## Documentação

- `docs/ARCHITECTURE.md` — arquitetura e fluxo de dados
- `docs/API.md` — referência da API própria
- `docs/TRAINING.md` — dataset, tokenizer e treino
- `docs/SECURITY.md` — camadas de segurança
- `docs/DEPLOYMENT.md` — deploy honesto
- `docs/HARDWARE.md` — requisitos de hardware e plano de escala
- `docs/ROADMAP.md` — o que está no horizonte (e o que foi **recusado** e por quê)
- `docs/historical/REMOVED_LEGACY.md` — inventário histórico do código antigo removido
