# ARKHER no SEU Windows: backend :8710 + agente :8765 + HTTPS :8443 (Vercel).
# Nao e GitHub Actions 24h. Nao depende de Tailscale Serve (401 do runneradmin).
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
$TsHost = "arkher-windows-24.tail91d201.ts.net"

function Get-Tailscale {
  $c = Get-Command tailscale -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  $p = "C:\Program Files\Tailscale\tailscale.exe"
  if (Test-Path $p) { return $p }
  return $null
}

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

  $ts = Get-Tailscale
  if ($ts) {
    try {
      $j = & $ts status --json 2>$null | ConvertFrom-Json
      if ($j.Self.DNSName) { $TsHost = ($j.Self.DNSName).TrimEnd(".") }
    } catch { }
    $crt = Join-Path $TokenDir "$TsHost.crt"
    $key = Join-Path $TokenDir "$TsHost.key"
    & $ts cert --cert-file $crt --key-file $key $TsHost 2>&1 | Out-Host
    $env:ARKHER_TS_HOST = $TsHost
    $env:ARKHER_TLS_CRT = $crt
    $env:ARKHER_TLS_KEY = $key
    $hs = Get-NetTCPConnection -LocalPort 8443 -ErrorAction SilentlyContinue
    if (-not $hs) {
      if ((Test-Path $crt) -and (Test-Path $key)) {
        Start-Process -FilePath $Py -WorkingDirectory $Root -ArgumentList @((Join-Path $Root "workers\workspace\https_ponte.py")) -WindowStyle Minimized
        Write-Host "HTTPS Vercel: https://${TsHost}:8443"
      } else {
        Write-Host "tailscale cert falhou. No admin Tailscale: DNS -> Enable HTTPS. Sem isso o site vercel.app nao fala com o PC."
      }
    }
    netsh advfirewall firewall delete rule name="ARKHER HTTPS 8443" 2>$null | Out-Null
    netsh advfirewall firewall add rule name="ARKHER HTTPS 8443" dir=in action=allow protocol=TCP localport=8443 2>$null | Out-Host
  } else {
    Write-Host "Tailscale nao encontrado. Sem certificado o Vercel (HTTPS) nao alcanca o PC."
  }
  Write-Host "Agente token em $TokenFile"
  Write-Host "Celular: Tailscale ligado + https://arkherai-resynced.vercel.app"
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
