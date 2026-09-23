# API própria do ARKHER

Base: `/api`. Autenticação: `Authorization: Bearer ark_...` (emitido em `/api/auth/device`).
Erros seguem o formato `{ "ok": false, "code": "...", "message": "..." }`.

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/api/health` | Estado do backend + estado do modelo (público) |
| GET | `/api/version` | Versão da ARKHER |
| GET | `/api/model/status` | Estado detalhado e honesto do modelo próprio |
| POST | `/api/model/load` | Dispara carregamento (409 se não houver checkpoint) |
| POST | `/api/auth/device` | Cria identidade local e token |
| POST | `/api/chat` | Conversa — resposta em **SSE** (`meta`, `token`, `done`, `error`) |
| POST | `/api/chat/stop` | Cancela geração pelo `gen_id` |
| GET/POST | `/api/sessions` | Lista/cria conversas |
| GET/PATCH/DELETE | `/api/sessions/{id}` | Lê/renomeia/exclui conversa |
| GET/POST | `/api/memory` | Lista (com `?q=`)/salva memória (exige `consent: true`) |
| DELETE | `/api/memory/{id}` | Esquece memória |
| DELETE | `/api/memory` | Apaga todas |
| GET | `/api/memory/export` | Exporta memórias |
| GET | `/api/tools` | Ferramentas + estado de autorização |
| POST | `/api/tools/{id}/authorize` | Autoriza ferramenta |
| POST | `/api/tools/{id}/revoke` | Revoga autorização |
| GET | `/api/tools/history` | Histórico auditado de uso |
| POST | `/api/tools/{id}/run` | Executa ferramenta validada |
| POST | `/api/tools/files` | Envia arquivo para a sandbox do usuário |
| GET | `/api/training/status` | Estado real do treinamento no servidor |
| POST | `/api/training/start` | Executa etapa (`prepare`…`report`) |
| GET | `/api/training/log` | Log da etapa |
| GET | `/api/diagnostics` | Diagnóstico sem segredos |

## `POST /api/chat`

Corpo: `{ message, session_id?, memory_enabled, replace_last_user? }`
Limites: mensagem ≤ 4000 caracteres (413 honesto), rate limit por usuário.

Eventos SSE:
```
event: meta   → {gen_id, session_id}
event: token  → {t}            (vários)
event: done   → {content, kind, metrics?, cancelled?}
event: error  → {code, message}
```

Quando o modelo próprio não está instalado, o stream devolve exatamente:
```json
{ "ok": false, "code": "MODEL_NOT_INSTALLED",
  "message": "O modelo próprio do ARKHER ainda não está instalado neste servidor." }
```
Nunca há resposta simulada nem fallback externo.
