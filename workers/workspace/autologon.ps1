# Auto-logon Windows da VM ARKHER. Rode como Administrador UMA vez.
# Uso: .\autologon.ps1 -User "seuuser" -Password "..."
param(
  [Parameter(Mandatory=$true)][string]$User,
  [Parameter(Mandatory=$true)][string]$Password
)
$ErrorActionPreference = "Stop"
$path = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
Set-ItemProperty $path -Name AutoAdminLogon -Value "1"
Set-ItemProperty $path -Name DefaultUserName -Value $User
Set-ItemProperty $path -Name DefaultPassword -Value $Password
Write-Host "ARKHER: AutoAdminLogon ativo para $User. Reinicie a VM."
