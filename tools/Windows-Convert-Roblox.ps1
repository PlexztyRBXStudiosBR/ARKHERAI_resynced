# ARKHER — conversão em lote .rbxl→.rbxlx / .rbxm→.rbxmx
# Uso: .\tools\Windows-Convert-Roblox.ps1 -Root "$env:USERPROFILE\Documents\ArkherAITraining"
[CmdletBinding()] param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference = "Continue"
$Root = (Resolve-Path $Root).Path
$Repo = Split-Path $PSScriptRoot -Parent
if (-not $Repo) { $Repo = (Get-Location).Path }
$Py = Join-Path $Repo "tools\rbx_convert.py"
if (-not (Test-Path $Py)) { $Py = Join-Path $PSScriptRoot "rbx_convert.py" }
if (-not (Test-Path $Py)) { throw "nao achei tools/rbx_convert.py" }
$exe = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $exe) { $exe = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $exe) { throw "python nao esta no PATH" }
& $exe.Source $Py $Root --recursivo
if ($LASTEXITCODE -ne 0) { Write-Host "alguns arquivos nao converteram (veja as linhas 'nao')" }
