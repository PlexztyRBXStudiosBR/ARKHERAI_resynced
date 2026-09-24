# Acervo Roblox no Android

Pasta informada:

```text
/storage/emulated/0/ArkherAITraining
```

No Termux, rode:

```bash
python roblox_dataset_ingest.py /storage/emulated/0/ArkherAITraining --once
```

Para monitorar novas cópias continuamente:

```bash
python roblox_dataset_ingest.py /storage/emulated/0/ArkherAITraining --interval 120
```

O script cria dentro da pasta:

```text
_arkher/
├── originais/   # cópias com hash, nunca apaga os arquivos originais
├── rbxlx/       # XML convertido ou já existente
├── rbxmx/       # XML convertido ou já existente
├── previews/    # reservado para renders do Studio
├── indices/     # manifest.json
└── pendencias/  # binários que aguardam conversor
```

## Conversão automática

O script detecta `.rbxl`, `.rbxm`, `.rbxlx` e `.rbxmx`. Para converter binários
é necessário um conversor que realmente entenda o formato Roblox. No Termux,
configure um comando externo com os placeholders `{input}`, `{output}` e
`{kind}`:

```bash
export ARKHER_RBXL_CONVERTER='SEU_CONVERSOR --input "{input}" --output "{output}"'
python roblox_dataset_ingest.py /storage/emulated/0/ArkherAITraining
```

Sem conversor, o sistema preserva o original e cria uma pendência. Ele nunca
renomeia um `.rbxl` para `.rbxlx` fingindo que converteu.

## Sobre o viewport visual

O extractor estrutural não substitui o renderizador Roblox. Para a IA realmente
ver geometria, materiais, iluminação, UI e animações, o pipeline precisa de um
executor do Studio autorizado para abrir cada XML e exportar previews: visão
geral, interiores, detalhes, materiais, personagens e frames de animação.

O Android pode armazenar e organizar o acervo, mas não consegue renderizar
fielmente um jogo Roblox apenas com Python. A etapa visual deve rodar no Roblox
Studio em uma máquina onde ele esteja instalado, ou por um exportador de
previews que você execute manualmente. Os resultados entram em `_arkher/previews`
e são ligados pelo manifest ao Model/Instance correspondente.

A ARKHER pode então usar dois canais juntos:

```text
estrutura XML + scripts + grafo
        +
previews visuais + assets autorizados + frames de animação
```

Isso permite correlacionar o que o objeto é, como está organizado, como parece
e como se comporta. Arquivos privados e assets sem licença não devem ser
publicados nem misturados ao dataset redistribuível.
