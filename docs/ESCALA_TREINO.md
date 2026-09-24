# Escala do ARKHER — como a gente compete (a régua certa)

## O eixo de competição (corrigido)

O ARKHER **não** disputa corrida de parâmetros/datacenter com modelos de
fronteira — essa régua foi um erro de enquadramento. A disputa real é em:

- **Eficiência** — fazer mais com menos (ferramentas reais em vez de "imaginar" a saída);
- **Controle** — a IA age DENTRO das ferramentas abertas do usuário (Blender,
  Roblox Studio), peça por peça, com permissão, como um profissional faria;
- **Liberdade** — sem provedor externo no runtime; o produto é seu;
- **Aprendizado dinâmico** — ciclos contínuos de treino com dados licenciados,
  checkpoint acumulando entre sessões, operários avaliando e corrigindo;
- **Potencial** — a cada ciclo e a cada ferramenta integrada, o teto sobe.

É por isso que "controlar o Blender de verdade com todas as ferramentas dele"
vale mais que um gerador 3D de uma chamada só: é trabalho de profissional,
iterado, testado e corrigido — não palpite de uma amostra.

## O que já sustenta isso hoje

| Peça | Estado |
|---|---|
| Ferramentas reais (Blender `.py`, `.rbxlx`, `.obj`, pontes ao vivo) | ✅ funcionando |
| Treino por checkpoint (retoma de onde parou, acumula entre sessões) | ✅ funcionando |
| Rede de nós (Kaggle T4/P100 ~30h GPU/sem, Colab, Lightning, seu PC) | ✅ `workers/` |
| **Operários HF** (`workers/hf_operarios/`): modelos abertos geram/avaliam/filtram dados de treino com proveniência | ✅ novo |
| Camada de verificação de resposta (corrige aritmética, alegações falsas) | ✅ `security/guard.py` |
| Render 3D real via Blender headless | ✅ `workers/render/` |
| Observatório de treino (gráficos + news, atualiza só quando você pede) | ✅ aba Cérebro/Treino |

## A escada de capacidade (mesmo pipeline, degraus)

| Degrau | Tamanho | Dados | Compute | Ganho real |
|---|---|---|---|---|
| 1. Mini (atual) | ~4M | ~130k tokens | CPU / T4 | nicho game dev + ferramentas |
| 2. Small | ~30–50M | 5–20M tokens licenciados | 1 GPU 8–12 GB | bem menos repetição, código melhor |
| 3. Medium | ~300M–1B | 10–50B tokens licenciados | dezenas de sessões P100/A100 | assistente geral razoável |
| 4. Multimodal (ver imagem/vídeo) | encoder + o modelo atual | pares imagem↔texto licenciados | GPU média | "olhar" referência e modelar a partir dela |
| 5. Fronteira | 70B+ | 5–15T tokens | datacenter | fora do escopo individual — irrelevante pro nosso jogo |

O degrau 4 é o caminho honesto para o "all-in-one" (texto, imagem, 3D,
animação, textura): um encoder de visão acoplado ao ARKHER, treinado com pares
licenciados — mesma filosofia de ferramenta própria, sem depender de GPU de
terceiro no runtime (a renderização pesada continua nos nós Kaggle/Blender).

## O que NÃO entra, e não é falta de ambição

São travas que protegem a conta e o produto — sem elas tudo acima cai:

- **IA controlando PC/VM/remoto** (inclui "gerar PCs no GitHub Actions"):
  runner de CI é para build, não máquina pessoal; automatizar isso viola os
  termos → ban da conta que hospeda tudo. A alternativa legítima (serviço
  sempre ligado que se auto-recupera) está em `docs/DEPLOYMENT.md`.
- **Varrer a web inteira / transcrições de vídeo sem licença**: o treino usa só
  fontes com licença declarada (`model/datasets/fontes.py`); é o porteiro que
  mantém o dataset publicável.
- **Operário = inteligência externa no runtime**: operários HF existem SÓ no
  treino, rodando no seu hardware; o modelo servido continua 100% próprio.
- **Executors/trapaças**: prejudicam outros jogadores — recusa permanente.

## Resposta curta

> O ARKHER compete aprendendo de verdade e agindo de verdade: ferramentas
> abertas controladas com permissão + ciclos contínuos de treino com operários
> e checkpoints. Não promete "ficar igual ao Claude" em raciocínio geral —
> promete ser o mais forte no nicho (game dev) e subir degrau por degrau,
> medido, sem depender de nenhum provedor externo.
