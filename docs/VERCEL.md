# Publicar o site do ARKHER AI na Vercel (passo a passo)

O site é **frontend estático + backend com modelo próprio**. Na Vercel entra o
frontend; o modelo continua rodando no SEU backend (PC, VM sua ou Docker),
porque o produto não depende de nenhum provedor externo.

## 1. Backend no ar (uma vez)

```bash
docker compose up --build                       # ou deploy/arkher.service (systemd)
```

Libere o domínio da Vercel no CORS do backend:

```bash
ARKHER_CORS_ORIGINS="https://SEU-PROJETO.vercel.app,http://localhost:5173"
```

(veja `docs/DEPLOYMENT.md` para as opções de "sempre ligado")

## 2. Frontend na Vercel

1. Vercel → **Add New → Project** → importe este repositório
   (`PlexztyRBXStudiosBR/ARKHERAI_resynced`, branch `arena/01a0cf78-arkherai-resynced`);
2. **Root Directory:** `frontend`
3. Framework: **Vite** (detectado automaticamente) — Build: `npm run build` — Output: `dist`
4. Deploy.

## 3. Apontar o site para o seu backend

Abra o site publicado → aba **Config** → campo *"Endereço do backend próprio"* →
cole `https://SEU-BACKEND` (ou `http://IP:8710` na sua rede) → pronto.
O estado real do modelo aparece na barra de status (Pronta / Modelo carregando /
Backend offline — sempre honesto, nunca tela infinita).

## Onde fica cada ferramenta (mapa rápido)

| Ferramenta | Onde usar |
|---|---|
| Chat com modelo próprio, /comandos e intenção natural | aba **Conversa** |
| Blender (cena/personagem/terreno/animação/texturas 4K), terreno OBJ, places Roblox, receitas de terreno/animação/estilo/física do Arkher Studio | aba **3D** |
| Pontes (plugin Studio, addon Blender), render nodes, rede de treino, HF, sempre-ligado, Arkher Studio | aba **Integrações** |
| Gráficos do treino, news de checkpoints, memória neural, status do produto | aba **Cérebro** |
| Autorização/histórico das 15 ferramentas do backend | aba **Ferramentas** |
| Tema, idioma, backend, limites do produto, diagnóstico | aba **Config** |

Sem backend, o site mostra erro claro e não finge resposta — é o comportamento
proposital do produto (`MODEL_NOT_INSTALLED` honesto).
