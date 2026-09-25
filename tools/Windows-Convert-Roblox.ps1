# ARKHER AI - conversao em lote no Windows
# Uso: .\Windows-Convert-Roblox.ps1 -Root "$env:USERPROFILE\Documents\ArkherAITraining"
[CmdletBinding()] param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference = "Continue"
$Root=(Resolve-Path $Root).Path
$Tool=(Get-Command rbx-util -ErrorAction SilentlyContinue)
if(-not $Tool){ throw "rbx-util nao encontrado. Instale o binario Windows do rbx-dom e adicione ao PATH." }
$ark=Join-Path $Root "_arkher"
$orig=Join-Path $ark "originais"; $xml=Join-Path $ark "convertidos"; $err=Join-Path $ark "pendencias"
New-Item -ItemType Directory -Force $orig,$xml,$err | Out-Null
$rows=@()
Get-ChildItem -LiteralPath $Root -Recurse -File | Where-Object { $_.FullName -notlike "$ark\*" -and $_.Extension.ToLower() -in @('.rbxl','.rbxm','.rbxlx','.rbxmx') } | ForEach-Object {
  $f=$_; $kind=$f.Extension.ToLower(); $hash=(Get-FileHash $f.FullName -Algorithm SHA256).Hash.ToLower()
  $row=[ordered]@{arquivo=$f.FullName;tipo=$kind;sha256=$hash;status=''
    saida=''}
  if($kind -in @('.rbxlx','.rbxmx')) { $row.status='xml_existente'; $row.saida=$f.FullName }
  else {
    $outExt=if($kind -eq '.rbxl'){'.rbxlx'}else{'.rbxmx'}
    $out=Join-Path $xml ($f.BaseName+$outExt)
    & $Tool.Source convert $f.FullName $out 2>&1 | Out-File (Join-Path $err ($f.BaseName+'.log')) -Encoding utf8
    if(Test-Path $out) { $row.status='convertido'; $row.saida=$out } else { $row.status='falhou'; $row.saida='' }
  }
  $rows += [pscustomobject]$row
}
$rows | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $ark 'conversion_manifest.json') -Encoding utf8
Write-Host "ARKHER: $($rows.Count) arquivos processados. Manifesto: $ark\conversion_manifest.json"
