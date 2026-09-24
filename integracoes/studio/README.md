# Integração ARKHER AI ⇄ Arkher Studio

O Arkher Studio (repo `PlexztyRBXStudiosBR/ia`, branch `arena/01a0d0ac-ia`)
já tinha uma rota `arkherai.js` apontando para o ARKHER — mas em modo mock e
com um import quebrado de `node-fetch`. Este pacote completa a integração REAL.

## Conteúdo

| Arquivo | Papel |
|---|---|
| `arkher_studio_integracao.patch` | Patch único (git format-patch): rotas `/real/*` no Node + módulo Luau + docs |
| `ArkherAIConnector.luau` | Módulo Luau para o Roblox falar DIRETO com o backend ARKHER |
| `arkherai.js` | Versão completa e patcheada da rota (referência) |

## Aplicar no repo `ia` (2 minutos)

```bash
git clone https://github.com/PlexztyRBXStudiosBR/ia.git
cd ia
git checkout arena/01a0d0ac-ia
git am /caminho/para/arkher_studio_integracao.patch
```

Ou manualmente (3 arquivos):

1. `backend/src/routes/arkherai.js` ← substituir pela versão daqui;
2. `src/shared/ArkherAI/ArkherAIConnector.luau` ← novo;
3. `docs/ARKHER_AI_INTEGRATION.md` ← novo.

## Ligar

```bash
# no backend do Arkher Studio (backend/.env):
ARKHER_AI_BACKEND=http://SEU_SERVIDOR:8710   # onde o ARKHER AI roda
ARKHER_AI_MOCK=false                         # opcional: desliga os mocks antigos
```

Endpoints novos (todos funcionam mesmo com mock ativo no resto):

- `POST /api/arkherai/real/chat` — conversa real (SSE consumido → JSON)
- `POST /api/arkherai/real/build/start` — `{tema, seed}` → build por tema livre
- `GET  /api/arkherai/real/build/proximo` — operações peça a peça
- `GET  /api/arkherai/real/model/status` — estado real do modelo

## Dentro do Roblox

```lua
local ArkherAI = require(script.Parent.ArkherAIConnector)
ArkherAI.Configurar("http://SEU_SERVIDOR:8710")

local ok, resposta = ArkherAI.Chat("crie um castelo medieval com torres")

local okBuild, build = ArkherAI.Construir("base militar completa", 9)
if okBuild then
    local pasta = ArkherAI.Materializar(build.ops) -- Folder com as Parts
end
```

`Materializar` devolve um `Folder` de `Part` — plugue no `BuildingService`,
no `World` do ECS ou direto no Workspace. O ARKHER entrega as operações; quem
monta é o seu código (permissão e controle ficam com você).

## Testado de ponta a ponta

- status do modelo real ✓
- `castelo medieval` → **149 peças** (muralhas, torres, portão, interior) ✓
- chat real sem mock ✓
- backend fora → erro 502 honesto (nunca resposta inventada) ✓
