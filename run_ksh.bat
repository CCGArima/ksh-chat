@echo off
title KSH Private Console Chat
color 0C
taskkill /F /IM ssh.exe >nul 2>&1
python ksh.py
taskkill /F /IM ssh.exe >nul 2>&1
pause
