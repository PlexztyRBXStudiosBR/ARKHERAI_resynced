# Treinamento do ARKHER-1

O treinamento pertence ao projeto e roda **somente em servidor autorizado** —
nunca no navegador do usuário. Todo passo é reproduzível e versionado.

## Pipeline

```bash
PYTHONPATH=. .venv/bin/python -m model.datasets.generate_arithmetic  # dados sintéticos (seed fixa)
PYTHONPATH=. .venv/bin/python -m model.training.prepare_dataset      # corpus final
PYTHONPATH=. .venv/bin/python -m model.training.validate_dataset     # licença, segredos, PII
PYTHONPATH=. .venv/bin/python -m model.training.train_tokenizer      # BPE próprio (bpe_v1)
PYTHONPATH=. .venv/bin/python -m model.training.init_weights         # checkpoint não-treinado
PYTHONPATH=. .venv/bin/python -m model.training.train --epochs N     # treino
PYTHONPATH=. .venv/bin/python -m model.training.train --resume model/checkpoints/X.pt
PYTHONPATH=. .venv/bin/python -m model.training.evaluate             # perda/perplexidade
PYTHONPATH=. .venv/bin/python -m model.training.report               # relatório md
```

Estado ao vivo em `model/checkpoints/training_state.json` — é o que a aba
**Treino** do site mostra (botão *Atualizar* consulta apenas quando você pede).

## Dataset
- Origem e licença declaradas em `model/datasets/seed/dataset.yaml`.
- Conteúdo autoral do projeto + aritmética sintética (gerador com seed fixa).
- **Proibido**: raspar sites, dados pessoais ou conteúdo protegido sem autorização.
- `validate_dataset.py` bloqueia segredos e PII; `scrub_secrets.py` limpa textos novos.

## Checkpoints
- Arquivo `.pt` contém: versão, qualidade, config da arquitetura, pesos e meta
  (git do código, hash do dataset, passos, perdas).
- `latest.pt` é o checkpoint servido pelo runtime; nomeie por versão
  (`arkher1-mini-v0.1.0-demo.pt`).

## Escala honesta
O demo foi treinado em CPU num corpus de ~40 mil tokens. Para evoluir a qualidade
mantendo o mesmo pipeline, aumente dataset autorizado e compute — ver `HARDWARE.md`.
Nada disso muda o contrato: o modelo continua 100% próprio, sem pesos externos.
