# Site na Vercel + PC em casa

O Chrome na Vercel (HTTPS) nao fala com `http://`. No celular use o site do PC:

`http://arkher-windows-24.tail91d201.ts.net:8710`

## Ligar (sem PowerShell, sem admin)

```text
cd C:\Users\nexus\ARKHERAI_resynced
scripts\arkher-ligar.cmd
```

Ou duas janelas:

```text
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8710
.\.venv\Scripts\python.exe workers\workspace\agent.py
```
