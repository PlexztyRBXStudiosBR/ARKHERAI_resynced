@echo off
REM Sobe site :8710 e agente :8765. Sem admin, sem schtasks, sem firewall.
cd /d C:\Users\nexus\ARKHERAI_resynced
if not exist .venv\Scripts\python.exe (
  echo falta .venv
  exit /b 1
)
set PYTHONPATH=C:\Users\nexus\ARKHERAI_resynced
set ARKHER_WIN_USER=nexus
start "ARKHER site" .venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8710
start "ARKHER agente" .venv\Scripts\python.exe workers\workspace\agent.py
echo site  http://arkher-windows-24.tail91d201.ts.net:8710
echo agente :8765
