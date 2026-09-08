#!/bin/bash
cd "$(dirname "$0")"
python3 -c "import sys" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "======================================================="
    echo "[ОШИБКА] Python 3 не установлен!"
    echo "Пожалуйста, установите Python с сайта python.org"
    echo "======================================================="
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

python3 -c "import websockets" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Установка компонентов для Облачного чата..."
    python3 -m pip install -q websockets >/dev/null 2>&1
fi

echo "Очистка старых туннелей..."
pkill -f "pinggy" >/dev/null 2>&1

python3 ksh.py
if [ $? -ne 0 ]; then
    echo ""
    echo "======================================================="
    echo "[!] Работа программы была завершена с ошибкой."
    echo "Пожалуйста, скопируйте текст ошибки выше и отправьте разработчику."
    echo "======================================================="
fi
pkill -f "pinggy" >/dev/null 2>&1
echo ""
read -p "Нажмите Enter для выхода..."
