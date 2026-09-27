# Site na Vercel + PC em casa

O frontend publica na Vercel (`https://arkherai-resynced.vercel.app`).
O Chrome **bloqueia** `http://` a partir de uma página `https://` (mixed content).
Por isso o PC sobe um HTTPS próprio na **8443** com certificado Tailscale
(`workers/workspace/https_ponte.py`). Não usa Tailscale Serve (na VM o Serve
está preso no `runneradmin`).

## No PC (uma vez)

```powershell
cd C:\Users\nexus\ARKHERAI_resynced
git pull
powershell -ExecutionPolicy Bypass -File scripts\arkher-pc.ps1 -Tarefa
```

Isso sobe uvicorn `:8710`, agente `:8765` e ponte HTTPS `:8443`.
Se `tailscale cert` falhar: admin Tailscale → **DNS → Enable HTTPS**.

Firewall: porta **8443** TCP entrada.

## No celular

1. App **Tailscale** ligado (mesma conta / mesma cauda).
2. Chrome: `https://arkherai-resynced.vercel.app`
3. Não cole URL de backend. O site usa `https://arkher-windows-24.tail91d201.ts.net:8443`.

Toque no Workspace vai direto nessa HTTPS (localhost no PC encaminha ao `:8765`).
