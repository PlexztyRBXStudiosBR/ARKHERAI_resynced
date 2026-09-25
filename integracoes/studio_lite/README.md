# ARKHER AI no Studio Lite

## Instalacao pelo Command Bar

Abra o Studio Lite em modo de edicao, abra o Command Bar, cole o conteúdo de:

```text
InstalarArkherAI_CommandBar.luau
```

Execute uma vez.

## Onde cada coisa fica

| Item | Local |
|---|---|
| `ArkherAI` | `ReplicatedStorage/ArkherAI` |
| `Config` | `ReplicatedStorage/ArkherAI/Config` |
| `ClientBridge` | `ReplicatedStorage/ArkherAI/ClientBridge` |
| `Events`, `Assets`, `Cache`, `Generated`, `Knowledge` | dentro de `ReplicatedStorage/ArkherAI` |
| `ArkherAI_Server` | `ServerScriptService/ArkherAI_Server` |
| `ArkherAI_ToolbarClient` | `StarterPlayer/StarterPlayerScripts` |
| `ArkherAI_Toolbar` | `StarterGui` |

O script é idempotente: executar novamente atualiza os módulos sem criar cópias
com nomes diferentes.

## Configuração

Edite `ReplicatedStorage/ArkherAI/Config`:

```lua
return {
    Backend = "http://127.0.0.1:8710",
    StudioProxy = "http://127.0.0.1:3000/api/arkherai",
    Enabled = true,
    Token = "",
}
```

No celular, `127.0.0.1` aponta para o próprio celular. O backend/proxy precisa
estar rodando no Termux no mesmo aparelho ou o endereço deve ser trocado pelo
endereço acessível na rede local. Nunca coloque uma URL externa diretamente no
código do jogo se o proxy relativo puder ser usado.

## Limitação importante do botão de editor

Um jogo Roblox consegue criar UI em `StarterGui`, mas não consegue, por um
script de jogo comum, modificar a barra de ferramentas do editor depois de
voltar do Play. Essa barra é uma UI do editor, não do jogo. Portanto o instalador
cria o painel e a ponte, mas o botão **real** ao lado de “Voltar para
Crescendo” exige uma API de plugin/editor exposta pelo Studio Lite.

Se o Studio Lite tiver uma API de editor, o botão deve chamar:

```lua
ArkherAI:Toggle()
```

com estilo preto e borda dourada. Se não tiver, o botão instalado funciona como
UI do jogo durante execução e o painel pode ser aberto pelo caminho fornecido
pelo próprio Studio Lite.

## Renderizador e importação

O Studio Lite não precisa importar o projeto inteiro. O pipeline externo pode
ler `.rbxlx` e `.rbxmx`, extrair a estrutura e gerar um viewport próprio. Para
`.rbxl` e `.rbxm` binários, primeiro é preciso um conversor real do Roblox.
`rbx_util` instalado via Cargo só estará disponível se o diretório estiver no
PATH:

```bash
export PATH="$HOME/.cargo/bin:$PATH"
which rbx_util
```

Se o binário instalado suportar a operação necessária, configure o ingestador:

```bash
export ARKHER_RBXL_CONVERTER='rbx_util --input "{input}" --output "{output}"'
```

Confirme a sintaxe com:

```bash
rbx_util --help
```

O ARKHER não declara que uma conversão ocorreu sem verificar o arquivo de saída.

A visão completa exige duas entradas:

```text
estrutura XML + scripts + grafo
previews renderizados + materiais + texturas + frames de animação
```

O extractor pode analisar a primeira. A segunda precisa ser gerada por um
renderizador Roblox/Studio ou por um exportador de viewport compatível. O
Android organiza e armazena o acervo; ele não renderiza fielmente o motor
Roblox apenas com Luau/Python.

## Segurança

O painel não executa código recebido da IA. Construções passam por operações
permitidas e confirmação do jogo. Não use isso para executar scripts de
terceiros, trapacear ou controlar outros jogos.
