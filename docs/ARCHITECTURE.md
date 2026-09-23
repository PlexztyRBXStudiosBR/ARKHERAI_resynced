# Arquitetura do ARKHER AI

```
Navegador ──HTTPS──► Backend ARKHER (FastAPI) ──► Modelo próprio ARKHER-1
   │                      │  │  │
   │                      │  │  └─ Ferramentas validadas (sandbox)
   │                      │  └──── Memória por usuário (SQLite)
   │                      └─────── Guardas de entrada/saída + rate limit
   └─ Frontend Vite/TS (bundle único, sem scripts de terceiros)
```

## Princípios
1. **Primeira-party**: o navegador só fala com `/api` do backend ARKHER. Nenhum SDK,
   CDN ou endpoint de IA externo.
2. **Honestidade de estado**: o sistema reporta `model_not_installed`,
   `model_loading`, `ready` ou `error` — e a interface mostra exatamente isso.
3. **Sem simulação**: sem modelo, o chat devolve erro claro `MODEL_NOT_INSTALLED`.
4. **Superfície pequena**: frontend sem framework, backend com dependências mínimas.

## Módulos

### Frontend (`frontend/`)
- `src/services/api.ts` — cliente HTTP + SSE com timeout (nunca carrega infinito).
- `src/state/store.ts` — máquina de estados da UI (`offline`, `backend_ready_model_missing`,
  `model_loading`, `ready`, `generating`, `error`).
- `src/app/md.ts` — markdown sanitizado (escapa tudo antes de formatar).
- `src/screens/*` — Conversa, Memória, Ferramentas, Treino, Config.

### Backend (`backend/app/`)
- `api/routes.py` — toda a API própria (ver `docs/API.md`).
- `auth/` — modo local: identidade de dispositivo + token bearer (hash SHA-256).
- `chat/service.py` — validação → guarda de entrada → ferramenta OU modelo próprio
  → streaming SSE → guarda de saída → persistência + métricas.
- `chat/knowledge.py` — recuperação textual **local** sobre o conhecimento semente
  do projeto (condiciona o modelo próprio; nenhum embedding externo).
- `model/runtime.py` — estados do modelo, carregamento com timeout, geração com
  cancelamento cooperativo e deadline.
- `memory/` — memória com consentimento, escopo por usuário, rejeição de segredos.
- `tools/registry.py` — calc (AST, nunca eval), leitura de arquivos em sandbox por
  usuário, análise de texto, exportação, consulta de memória; tudo auditado.
- `security/` — rate limit, guardas de conteúdo, redação de logs.
- `storage/db.py` — SQLite local (nada externo).

### Modelo (`model/`)
- `tokenizer/bpe.py` — BPE implementado do zero, versionado (`bpe_v1`).
- `architecture/transformer.py` — decoder-only de 4 camadas, 4 cabeças, d=256.
- `inference/engine.py` — carregamento de checkpoint local e geração com stop/cancel.
- `training/*` — preparação, validação, tokenizer, treino com retomada, avaliação, relatório.
- `datasets/seed/` — corpus autoral + gerador sintético, com licença declarada.

## Fluxo de uma mensagem
1. `POST /api/chat` valida token, tamanho e rate limit.
2. Guarda de entrada recusa categorias proibidas (ilegais, +18, trapaças/exploits, malware).
3. Comandos `/calc`, `/texto`, `/ler`, `/memoria`, `/exportar` vão para ferramentas
   autorizadas e auditadas.
4. Caso contrário: memória autorizada + recuperação local montam o prompt;
   o ARKHER-1 gera tokens por SSE até EOS, marcador de bloco, cancelamento ou timeout.
5. Guarda de saída verifica aritmética, alegações de ações e formata correções.
6. Mensagem persistida; métricas registradas **sem conteúdo**.
