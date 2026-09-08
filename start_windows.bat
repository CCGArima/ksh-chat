@echo off
title KSH Private Console Chat System

python --version >nul 2>&1
if errorlevel 1 (
    echo =======================================================
    echo [ОШИБКА] Python не установлен или не добавлен в PATH!
    echo Пожалуйста, скачайте и установите Python с сайта python.org
    echo Убедитесь, что при установке стояла галочка "Add Python to PATH".
    echo =======================================================
    pause
    exit /b
)

echo Очистка старых туннелей...
taskkill /F /IM ssh.exe >nul 2>&1

echo Запуск KSH Chat...
python ksh.py
if errorlevel 1 (
    echo.
    echo =======================================================
    echo [!] Работа программы была завершена с ошибкой. 
    echo Пожалуйста, скопируйте текст ошибки выше и отправьте разработчику.
    echo =======================================================
)
taskkill /F /IM ssh.exe >nul 2>&1
pause
