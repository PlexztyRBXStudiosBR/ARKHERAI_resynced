# Super Mecha Training — plano executável

O ARKHER agora tem um **orquestrador de treino contínuo**, em `model/training/auto_train.py`.
Ele não promete uma capacidade que ainda não foi medida: executa ciclos reais,
acumula checkpoints, permite avaliação e pode ficar ativo 24/7.

## Como iniciar

Na máquina autorizada que tem o checkout e os recursos de treino:

```bash
cd ARKHERAI_resynced
PYTHONPATH=. .venv/bin/python -m model.training.auto_train --pause 30
```

Cada ciclo faz:

1. prepara o corpus;
2. valida o dataset;
3. treina retomando `model/checkpoints/latest.pt`;
4. salva uma versão com tag `auto-c000001`, `auto-c000002`...;
5. avalia e gera relatório;
6. aguarda o próximo ciclo.

Parada segura, inclusive durante a espera:

```bash
touch model/checkpoints/AUTO_TRAIN_STOP
```

Para teste controlado, use `--cycles 1`. A aba Cérebro também tem a etapa
`auto_train`, que inicia **um ciclo**, evitando colocar um processo infinito
acidentalmente no servidor web.

## O que significa “contínuo” aqui

O ciclo é contínuo e o conhecimento do modelo é acumulado por checkpoint. O
pipeline só usa dados do corpus semente e dados adicionados com proveniência e
licença; não raspa a internet, não treina com respostas inventadas e não chama
IA externa no runtime. Ferramentas como Blender, Roblox Studio e avaliadores
podem gerar artefatos de treino apenas quando o operador os exporta e revisa.

## Escada de versões

Hoje o modelo é um mini experimental de aproximadamente 4 milhões de
parâmetros. O auto-trainer não finge que repetir épocas transforma 4M em
trilhões: para cada degrau é necessário alterar `model/config.yaml`, preparar
um corpus compatível, validar memória/tempo e medir um conjunto de testes.

A progressão planejada é: mini → 30–50M → 100M → 300M/1B, com uma tag de
checkpoint por degrau. O próximo modelo pode inicializar a partir do anterior
quando as formas dos pesos forem compatíveis; quando a arquitetura mudar,
usa-se transferência documentada ou inicialização nova — nunca um `resume`
incompatível. Degraus de centenas de milhões e trilhões exigem GPU/cluster,
energia, dados e tempo que o hardware indie atual não oferece. O sistema fica
preparado para workers autorizados (PC, Kaggle/Colab ou máquinas próprias), mas
não controla máquinas remotas nem inventa disponibilidade.

## Critérios de promoção

Uma versão só deve ser promovida se passar: perda de validação sem regressão,
testes de Luau/Python, tarefas de game-dev, segurança, proveniência dos dados,
latência e revisão humana. “Chegar ao nível X” não é um critério técnico
verificável; o que podemos perseguir honestamente é melhorar os testes e a
capacidade de operar as ferramentas do Studio a cada ciclo.

Estado em tempo real: `model/checkpoints/auto_train_state.json`,
`model/checkpoints/auto_train.log` e `training_state.json`.
