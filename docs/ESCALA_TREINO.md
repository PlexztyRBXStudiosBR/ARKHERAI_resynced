# Escala de treino do ARKHER-1 — a escada honesta

Pedido recorrente: "treinar até o modelo ficar nível Claude/fronteira".
Este documento responde com números, não com promessa.

## Onde estamos hoje (fato medido)

| Item | Valor real |
|---|---|
| Arquitetura | ARKHER-1 mini, transformer próprio |
| Parâmetros | **3.977.728** (~4M) |
| Corpus | ~128.661 tokens (autoral + sintético licenciado) |
| Hardware de treino | CPU (ou GPU do usuário via Kaggle/Colab) |
| Papel do modelo | assistente especializado em game dev, honesto sobre limites |

## Por que "nível Claude" não sai de um treino aqui

Modelos de fronteira (Claude, GPT, Gemini) têm:

- **dezenas a centenas de bilhões** de parâmetros (10.000x a 100.000x mais que o ARKHER-1 mini);
- **trilhões** de tokens de treino (milhões de vezes mais que o nosso corpus);
- clusters de milhares de GPUs por semanas/meses;
- RLHF/alinhamento feito por equipes dedicadas.

Nenhum `train --epochs X` neste repositório muda essa ordem de grandeza.
Qualquer produto que prometa "ficar igual ao Claude com um botão" estaria
mentindo — e o contrato do ARKHER é não mentir.

## A escada que REALMENTE funciona (degrau por degrau)

| Degrau | Tamanho | Dados necessários | Compute | Resultado esperado |
|---|---|---|---|---|
| 1. Mini (atual) | ~4M | ~130k tokens | CPU / sessão Kaggle T4 | nicho game dev: formata, resume, gera cenas/scripts simples |
| 2. Small | ~30–50M | 5–20M tokens licenciados | 1 GPU consumidor (8–12 GB) | respostas mais coerentes, menos repetição, melhor código |
| 3. Medium | ~300M–1B | 10–50B tokens licenciados | dezenas de sessões P100/A100 (Kaggle/aluguel) | assistente geral razoável; ainda abaixo de fronteira |
| 4. Large | 7B+ | 1T+ tokens | cluster multi-GPU semanas | aproxima-se de modelos comerciais antigos |
| 5. Fronteira | 70B+ | 5–15T tokens | datacenter | fora do escopo de um projeto individual — e tudo bem |

Cada degrau usa **exatamente o mesmo pipeline** deste repositório
(`prepare_dataset → validate_dataset → train → evaluate → report`);
só mudam `model/config.yaml`, corpus e hardware. O treino já suporta
`--resume`, então degraus são cumulativos.

## O que o projeto faz em vez de prometer milagre

1. **Ciclos contínuos de treino** no hardware do usuário (Kaggle ~30h GPU/semana
   gratuitas, Colab, PC próprio) — cada ciclo melhora o checkpoint real.
2. **Dataset licenciado e auditado** (`validate_dataset.py` bloqueia segredos,
   PII e conteúdo sem licença) — crescer dados sem risco legal.
3. **Avaliação real** (perda, perplexidade e testes de ponta a ponta) publicada
   na aba Cérebro — progresso medido, não sentido.
4. **Especialização**: ser excelente no nicho (Roblox, Blender, game dev)
   vale mais que ser medíocre tentando ser generalista.

## Resposta curta

> Não existe treino neste produto que transforme o modelo leve em modelo de
> fronteira — isso exigiria outra escala de dados, parâmetros e hardware.
> Existe, sim, uma escada real e medível: cada degrau acima deixa o modelo
> melhor que o anterior, com o mesmo pipeline e sem depender de nenhum
> provedor externo. É isso que o ARKHER executa.
