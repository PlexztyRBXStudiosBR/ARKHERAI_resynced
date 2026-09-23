# Requisitos e plano de hardware (honesto)

## O que roda hoje
- **Inferência** do ARKHER-1 mini (3,66 M parâmetros): CPU comum, ~2 GB de RAM.
  Este repositório foi testado em 2 núcleos / 3,8 GB.
- **Treino demo**: CPU, minutos por época num corpus de ~40 mil tokens.

## Para evoluir o modelo mantendo o mesmo pipeline

| Objetivo | Dataset autorizado | Compute realista |
| --- | --- | --- |
| Melhorar temas atuais (game dev) | 100 mil–1 M tokens autorais/licenciados | 1 GPU 8–16 GB, horas–dias |
| Conversacional pequeno | 1–10 M tokens curados | GPU 16–24 GB, dias |
| Amplo uso geral | dezenas de B tokens curados | cluster multi-GPU, semanas |

O ARKHER-1 cresce em camadas: a arquitetura aceita mais camadas/cabeças/contexto
via `model/config.yaml` sem trocar runtime, API ou interface.

## O que NÃO é plano do projeto (e por quê)
- **Fábrica de VMs em runners de CI** para treinar/servir: viola termos do serviço de
  CI e não fornece compute estável. Treino sério usa hardware dedicado ou nuvem contratada.
- **Enxame de contas externas** como "operários": viola termos dos serviços e a
  política de dados do projeto.
- **Raspagem em massa de sites/vídeos** para auto-treino: conflita com direitos
  autorais e com `model/datasets/seed/dataset.yaml`. O caminho aprovado é:
  conteúdo autoral, licenciado, ou sintético gerado por scripts do projeto.

Quando houver hardware maior, o mesmo pipeline (`prepare → validate → tokenizer →
train → evaluate → report`) escala sem reintroduzir nada disso.
