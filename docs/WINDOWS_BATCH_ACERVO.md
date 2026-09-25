# Conversao em lote no Windows

O `rbx-util` foi compilado corretamente no Termux. O executável chama-se
`rbx-util`, com hífen, e não `rbx_util`:

```text
rbx-util convert input.rbxl output.rbxlx
rbx-util convert input.rbxm output.rbxmx
rbx-util view-binary arquivo.rbxm
```

No Windows, instale uma build Windows do `rbx-util` e coloque a pasta do
executável no PATH. Confirme:

```powershell
Get-Command rbx-util
rbx-util --help
```

Depois copie a pasta do celular para:

```text
$env:USERPROFILE\Documents\ArkherAITraining
```

Execute:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\tools\Windows-Convert-Roblox.ps1 `
  -Root "$env:USERPROFILE\Documents\ArkherAITraining"
```

O script percorre subpastas, converte `.rbxl` para `.rbxlx` e `.rbxm` para
`.rbxmx`, preserva originais e cria:

```text
_arkher\conversion_manifest.json
_arkher\convertidos\
_arkher\pendencias\
```

A sintaxe usada pelo `rbx-util` é posicional:

```text
rbx-util convert input output
```

Não é `--input`/`--output`.

A conversão entende o DOM e as propriedades serializadas do Roblox. Ela não
renderiza o jogo: previews visuais precisam ser produzidos pelo Roblox Studio
ou pelo exportador de viewport. A próxima etapa é o plugin batch do Studio
abrir os XMLs convertidos, extrair scripts/estrutura e gerar as câmeras/previews
sem o usuário abrir cada arquivo manualmente.
