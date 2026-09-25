@echo off
setlocal EnableExtensions
set "ROOT=%~dp0.."
set "DATA=%USERPROFILE%\Documents\ArkherAITraining"
set "STOP=%ROOT%\model\checkpoints\AUTO_TRAIN_STOP"
if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo [ARKHER] Python do ambiente nao encontrado: %ROOT%\.venv\Scripts\python.exe
  exit /b 1
)
if exist "%STOP%" del /q "%STOP%"
if not exist "%DATA%" mkdir "%DATA%"
if not exist "%ROOT%\model\checkpoints" mkdir "%ROOT%\model\checkpoints"
set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
where rbx-util >nul 2>nul
if errorlevel 1 echo [ARKHER] aviso: rbx-util nao esta no PATH; conversao sera pendencia.
start "ARKHER Auto Training" /b "%ROOT%\.venv\Scripts\python.exe" -m model.training.auto_train --pause 30 --epochs 2
set /a LEFT=21600
:wait
if %LEFT% LEQ 0 goto stop
if exist "%STOP%" goto done
>nul timeout /t 30 /nobreak
set /a LEFT-=30
goto wait
:stop
if not exist "%STOP%" type nul > "%STOP%"
:done
echo [ARKHER] ciclo de 6 horas encerrado/parado com seguranca.
endlocal
