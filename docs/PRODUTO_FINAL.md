# ARKHER AI — distância honesta para o produto final

> Consulta ao vivo: `GET /api/produto/status` (autenticado) devolve este
> checklist calculado do estado real do sistema.

## 1. Pronto (código, testado e funcionando)

| Área | Estado |
|---|---|
| Interface completa (chat, memória, ferramentas, treino, config) com ícones próprios, visualizador 3D e mobile-first | ✅ |
| Backend próprio: API, auth por token, SSE, auditoria, guardas, rate limit | ✅ |
| Modelo próprio ARKHER-1 mini (tokenizer BPE próprio, sem pesos externos) | ✅ |
| Ferramentas de game dev: sistemas Luau, places .rbxlx, compositor aberto de construção, scripts Blender (cena/terreno/personagem/animação com textura) | ✅ |
| Pontes de construção ao vivo: plugin Roblox Studio + addon Blender (com permissão do usuário) | ✅ |
| Rede de nós: render 3D e treino em Kaggle/Colab/Lightning/seu PC, com retomada por checkpoint | ✅ |
| **Operários HF**: modelos abertos do HF Hub (no seu hardware) geram/avaliam/filtram dados de treino com proveniência — `workers/hf_operarios/` | ✅ |
| **Observatório de treino**: gráficos de perda + news de checkpoints/relatórios, atualização manual (`/api/training/news`) | ✅ |
| **Sempre ligado legítimo**: systemd Restart=always + healthcheck Docker + vigia de saúde (`deploy/`) | ✅ |
| Auto-treino com dados da web licenciados: Wikipédia, Gutenberg, Stack Exchange gamedev, Internet Archive (só item com licença declarada) | ✅ pipeline |
| Camada de verificação de resposta: corrige aritmética, alegações de ações não executadas e capacidades inexistentes | ✅ |
| Docker, documentação, PWA instalável, 60+ testes backend + 19 frontend + 17 de integração | ✅ |

## 2. O que falta — e NÃO é código (é execução sua)

Estes itens estão com tudo pronto do lado do código; dependem de rodar:

1. **Ciclos de treino na rede** (o salto real de qualidade): abrir os notebooks
   de `workers/` nas suas contas Kaggle/Colab, baixar as fontes licenciadas
   (`python -m model.datasets.fontes baixar …`) e retreinar. É isso que transforma
   o ARKHER-1 mini num modelo progressivamente mais capaz. Tempo: sessões de GPU,
   acumulando por checkpoint — dias/semanas de ciclos, não horas. A escada honesta
   de escala está em `docs/ESCALA_TREINO.md`.
2. **Publicar num lugar permanente**: `docker compose up --build` no seu PC ou
   numa VM **sua** (o preview deste sandbox é efêmero). ~30 min.
3. **Instalar as pontes na sua máquina**: plugin no Roblox Studio e addon no
   Blender (arquivos em `/api/build/plugin` e `/api/build/plugin-blender`). ~10 min.

## 3. O que falta — código novo (opcional, por prioridade)

| Item | Esforço estimado |
|---|---|
| Conector Godot (cenas .tscn a partir do mesmo stream de operações) | médio |
| Conectores Figma / Cascadeur (dependem das APIs/plugin deles) | médio/alto |
| Visualização de .glb no navegador (loader próprio) | médio |
| Empacotamento APK (PWA já instalável cobre 90% do caso) | baixo |
| Multiusuário público (contas, moderação extra) — só se abrir ao público | alto |

## 4. Fora do produto por decisão (não será construído)

- Busca em web **no runtime** (regra de projeto: zero chamadas externas;
  para treino, já existem as fontes licenciadas acima).
- Desktop remoto/VM hospedada em runner de CI, com religamento automático
  após o limite de horas (violação dos termos do serviço → risco real de ban;
  o mesmo resultado legítimo: sessões manuais + estado persistido em
  checkpoint/repositório, que já funciona).
- Ver/controlar a tela de uma VM pelo app com comandos de IA (agente de tela /
  controle remoto). **Alternativa legítima já entregue**: o ARKHER se mantém no
  ar sozinho na sua própria máquina — systemd `Restart=always`, Docker com
  healthcheck e o vigia `deploy/arkher-watchdog.sh` (ver `docs/DEPLOYMENT.md`).
- Shell arbitrário exposto na interface (superfície de invasão; as ferramentas
  autorizadas cobrem o que é seguro executar).

## Resumo em uma frase

O produto está **funcionalmente completo como v1**; a distância para o
"produto final potente" é, quase toda, **rodar os ciclos de treino e publicar**
— passos seus, com o caminho pronto — e não escrever mais código.
