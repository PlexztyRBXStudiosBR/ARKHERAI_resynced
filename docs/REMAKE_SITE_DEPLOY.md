# Remake ARKHER AI: Vercel + backend + workers

## Contrato de produção

```text
Vercel (frontend) → HTTPS → FastAPI persistente → worker Termux/PC autorizado
```

O Vercel hospeda a interface; não hospeda o treino longo, Uvicorn, Blender ou
jobs de render. O backend continua sem provedores externos no runtime.

## Vercel

Em Project Settings → Environment Variables:

```env
VITE_ARKHER_API=https://api.seu-dominio.com
```

Depois de alterar, faça novo deploy. O frontend deve usar essa variável; nunca
use `localhost` em código que roda no navegador do usuário.

## Backend

No servidor persistente:

```env
ARKHER_HOST=0.0.0.0
ARKHER_PORT=8710
ARKHER_CORS_ORIGINS=https://seu-site.vercel.app,https://seu-dominio.com
ARKHER_DATA_DIR=/var/lib/arkher/data
```

Verifique:

```bash
curl https://api.seu-dominio.com/api/health
```

## Worker

O Termux ou PC autorizado conversa com o backend por jobs autenticados. Ele
faz conversão, análise, render e treinamento. O site mostra status e relatórios;
não guarda senha de máquina nem token secreto no bundle.

## Abas do remake

As abas devem ser ligadas a contratos reais: Chat, Training, Render, Projects,
Roblox Analyzer, Animator, Texture Maker, Game Systems, Luau Lab, Terrain,
Benchmarks, Web Search, Integrations, Reports, Memory, Dataset, Files e Settings.
Uma integração sem credencial/teste deve aparecer como `não configurada`, não
como funcional.

## Machine Streaming

A sessão é temporária e iniciada pelo usuário. O backend só deve manter um
identificador de sessão expirável, estado e logs mínimos. A bridge de criação
no Roblox Studio/Blender deve ser plugin/add-on autorizado e pedir aprovação
antes de aplicar artefatos. Não coloque senhas ou IPs no frontend.
