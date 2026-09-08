@echo off
title KSH Private Console Chat
color 0C
python -c "import websockets" >nul 2>&1
if errorlevel 1 (
    echo [*] Installing required websockets library...
    python -m pip install -q websockets
)
taskkill /F /IM ssh.exe >nul 2>&1
python ksh.py
taskkill /F /IM ssh.exe >nul 2>&1
pause
