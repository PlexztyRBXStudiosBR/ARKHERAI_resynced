# RBXL Knowledge Extractor

Converte jogos locais funcionais em um pacote compacto, indexável e rastreável:

```bash
PYTHONPATH=. .venv/bin/python -m model.training.rbxl_knowledge \
  /caminho/para/meus_jogos \
  --out model/datasets/generated/rbxl_knowledge
```

Para `.rbxlx`, extrai:

- hierarquia e contagem de Instances;
- scripts `Script`, `LocalScript` e `ModuleScript`;
- nomes, linhas e chamadas `require`;
- RemoteEvents/RemoteFunctions;
- serviços importantes;
- hash, tamanho e formato;
- manifest de proveniência.

Para `.rbxl` binário, registra hash e informa honestamente que é necessário
usar no Studio **Save As → Roblox XML (.rbxlx)**. O extractor nunca executa
scripts do jogo.

O resultado fica em `manifest.json` e `scripts/`. O arquivo original pode ficar
fora do Git; o repositório deve guardar somente o índice, os testes e os
artefatos que podem ser redistribuídos. Antes de promover scripts ao treinamento,
verifique licença, segredos, IDs privados e aprovação do projeto.

Esse pacote alimenta o auto-training como fonte de casos reais. A próxima
camada pode executar testes e gerar variações, mas protótipos começam como
`aguarda_validacao`; uma saída do modelo nunca vira verdade automaticamente.
