# Rede de Treinamento ARKHER — o poder distribuído, organizado

> Nota de fronteira: `workers/` é infraestrutura de TREINO offline, executada
> manualmente nas contas do dono. Não faz parte do runtime do produto: o site e o
> backend continuam sem nenhuma chamada a provedor externo.

A ideia central do projeto está mantida: **a ARKHER fica mais potente somando
máquinas**, não dependendo de uma só. Esta pasta organiza a rede de treino em
nós que você controla, cada um no uso para o qual o serviço foi feito.

## Nós da rede

| Nó | O que roda | Por quê |
| --- | --- | --- |
| **Seu PC / este servidor** | `model/training/train.py` direto | nó zero, sempre disponível |
| **Kaggle** (GPU T4/P100 grátis) | `workers/kaggle/arkher_treino.ipynb` | GPU gratuita legítima para treino |
| **Kaggle** (render 3D) | `workers/kaggle/arkher_render.ipynb` | Blender real gera modelos/animações/texturas a partir dos scripts da ARKHER |
| **Google Colab** | `workers/colab/arkher_treino.ipynb` | idem, outra conta de GPU |
| **Lightning AI Studios** | `workers/lightning/treino.py` | créditos gratuitos de GPU |
| **Operários HF (qualquer GPU/CPU sua)** | `workers/hf_operarios/operarios_hf.py` | modelos abertos do HF Hub geram/avaliam/filtram dados de treino com proveniência |

**Como funciona o ciclo** ("ir religando e religando"):
1. O nó baixa o repositório (dataset + código + `latest.pt` versionado no git).
2. Retoma o treino do checkpoint (`--resume`), treina o máximo que a sessão permitir.
3. Salva o checkpoint novo + relatório; você (ou o sync) devolve ao repositório.
4. A sessão expirou? Abre de novo e repete — o estado viaja no checkpoint, não na máquina.

É assim que o aprendizado acumula entre sessões efêmeras, sem depender de nenhuma
máquina ficar ligada para sempre.

## Sincronização de checkpoints

- **Padrão (git)**: os checkpoints pequenos vivem versionados no repositório
  (`model/checkpoints/`). O nó faz `git pull` antes e você commita o resultado depois.
- **Opcional (depósito privado seu)**: `workers/sync/hf_sync.py` baixa/envia o
  checkpoint para um repositório PRIVADO criado por você, usando token guardado
  nos segredos do Kaggle/Colab (nunca no código).

## O que esta rede NÃO inclui (e por quê)

| Item | Status | Motivo objetivo |
| --- | --- | --- |
| Runner de CI como VM persistente (acesso remoto + religar por cron para burlar o limite) | ❌ fora | Viola os termos do serviço de CI; o padrão de religar a cada 5h existe justamente para burlar o corte de 6h. Resultado prático: repositório e conta banidos — o oposto de poder. |
| Agente com shell arbitrário, captura de tela e injeção de mouse/teclado | ❌ fora | É infraestrutura de acesso remoto genérica; o projeto nasceu removendo isso por segurança. |
| Túnel privado + firewall aberto + senha de admin impressa em log | ❌ fora | Superfície de ataque enorme sobre máquinas descartáveis. |

Se um dia você tiver uma máquina física sua dedicada, o script de treino roda nela
direto (ela é só mais um nó) — sem agente remoto nenhum.

## Expectativa honesta de ganho

- Este sandbox (2 CPUs): ~1,5 s/passo → modelo de 4 M parâmetros viável.
- 1× T4 no Kaggle: ~10–20× mais rápido → dá para treinar 20–50 M de parâmetros
  com corpus na casa dos milhões de tokens, em sessões de 9–12 h.
- Vários nós somados: o gargalo vira o DATASET autorizado — por isso o pipeline
  tem validação de licença/segredos/PII desde o início.
