# Junta .rbxl / .rbxlx do pack numa pasta de places do Studio (nexus).
# Nao publica na nuvem. Nao abre centenas de janelas.
#
#   powershell -ExecutionPolicy Bypass -File tools\studio_places.ps1
param(
  [string[]]$Root,
  [string]$Dest
)
$ErrorActionPreference = "Continue"
$HomeN = "C:\Users\nexus"
if (-not (Test-Path $HomeN)) { $HomeN = $env:USERPROFILE }
$Repo = Split-Path $PSScriptRoot -Parent
if (-not $Repo) { $Repo = (Get-Location).Path }
$PyScript = Join-Path $Repo "tools\studio_places.py"
$Py = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $Py) { $Py = (Get-Command python3 -ErrorAction SilentlyContinue).Source }

if ($Py -and (Test-Path $PyScript)) {
  $argsPy = @($PyScript)
  if ($Root) { $argsPy += $Root }
  if ($Dest) { $argsPy += @("-d", $Dest) }
  & $Py @argsPy
  $code = $LASTEXITCODE
} else {
  if (-not $Dest) { $Dest = Join-Path $HomeN "Documents\Roblox\ARKHER_Places" }
  New-Item -ItemType Directory -Force $Dest | Out-Null
  if (-not $Root) {
    $Root = @(
      (Join-Path $HomeN "ArkherAITraining"),
      (Join-Path $HomeN "Documents\ArkherAITraining"),
      (Join-Path $HomeN "Downloads"),
      (Join-Path $HomeN "Desktop")
    )
  }
  $n = 0
  foreach ($r in $Root) {
    if (-not (Test-Path $r)) { continue }
    Get-ChildItem -Path $r -Recurse -File -Include *.rbxl,*.rbxlx -ErrorAction SilentlyContinue |
      Where-Object { $_.FullName -notmatch '\\pendencias\\' } |
      ForEach-Object {
        $alvo = Join-Path $Dest $_.Name
        if (Test-Path $alvo) {
          $alvo = Join-Path $Dest ($_.BaseName + "_" + $_.Length + $_.Extension)
        }
        if (-not (Test-Path $alvo)) {
          try { New-Item -ItemType HardLink -Path $alvo -Target $_.FullName -ErrorAction Stop | Out-Null }
          catch { Copy-Item $_.FullName $alvo }
          $n++
        }
      }
  }
  Write-Host "$n places -> $Dest"
  $code = $(if ($n -eq 0) { 2 } else { 0 })
}

if (Test-Path (Join-Path $HomeN "Documents\Roblox\ARKHER_Places")) {
  Start-Process explorer.exe (Join-Path $HomeN "Documents\Roblox\ARKHER_Places")
}
exit $code
