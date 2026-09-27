# ARKHER no SEU Windows: backend + agente + Tailscale HTTPS, no logon.
# Nao e GitHub Actions 24h.
#
#   powershell -ExecutionPolicy Bypass -File scripts\arkher-pc.ps1 -Ligar
#   powershell -ExecutionPolicy Bypass -File scripts\arkher-pc.ps1 -Tarefa
param(
  [switch]$Ligar,
  [switch]$Tarefa
)
$ErrorActionPreference = "Continue"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $Py) { throw "python/.venv nao encontrado em $Root" }
$TokenDir = Join-Path $env:USERPROFILE "arkher_state"
New-Item -ItemType Directory -Force $TokenDir | Out-Null
$TokenFile = Join-Path $TokenDir "agent.token"
if (-not (Test-Path $TokenFile) -or -not (Get-Content $TokenFile -ErrorAction SilentlyContinue)) {
  $tok = "agt_" + (-join ((1..32) | ForEach-Object { "{0:x}" -f (Get-Random -Max 16) }))
  Set-Content -Path $TokenFile -Value $tok -Encoding ascii
}
$tok = (Get-Content $TokenFile -Raw).Trim()

function Start-Arkher {
  $env:PYTHONPATH = $Root
  $env:ARKHER_AGENT_TOKEN = $tok
  $env:ARKHER_CORS_ORIGINS = "https://arkherai-resynced.vercel.app,http://localhost:5173,http://127.0.0.1:5173"
  $uv = Get-NetTCPConnection -LocalPort 8710 -ErrorAction SilentlyContinue
  if (-not $uv) {
    Start-Process -FilePath $Py -WorkingDirectory $Root -ArgumentList @("-m","uvicorn","backend.app.main:app","--host","0.0.0.0","--port","8710") -WindowStyle Minimized
  }
  $ag = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue
  if (-not $ag) {
    Start-Process -FilePath $Py -WorkingDirectory $Root -ArgumentList @((Join-Path $Root "workers\workspace\agent.py")) -WindowStyle Minimized
  }
  $ts = Get-Command tailscale -ErrorAction SilentlyContinue
  if (-not $ts) { $tsPath = "C:\Program Files\Tailscale\tailscale.exe"; if (Test-Path $tsPath) { $ts = Get-Item $tsPath } }
  if ($ts) {
    & $ts.Source serve --bg 8710 2>$null
    $ip = (& $ts.Source ip -4 2>$null | Select-Object -First 1)
    Write-Host "ARKHER backend http://$($ip):8710"
    Write-Host "Tailscale Serve: rode 'tailscale serve status' e cole o https://….ts.net na Config do site da Vercel."
  } else {
    Write-Host "Tailscale nao encontrado. Sem HTTPS o site vercel.app NAO mostra a tela no celular."
  }
  Write-Host "Agente token em $TokenFile"
}

if ($Tarefa) {
  $script = Join-Path $PSScriptRoot "arkher-pc.ps1"
  $act = "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`" -Ligar"
  schtasks /Create /TN "ARKHER-PC" /TR $act /SC ONLOGON /RL LIMITED /F | Out-Host
  Write-Host "Tarefa ARKHER-PC no logon. Proximo login sobe sozinho."
  Start-Arkher
  return
}
if ($Ligar) { Start-Arkher; return }
Write-Host "use -Ligar (agora) ou -Tarefa (agora + todo logon)"
