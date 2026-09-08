#!/usr/bin/env bash
# KSH Chat 1-Click Launcher for macOS Finder
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"
pkill -f pinggy >/dev/null 2>&1
python3 -c "import websockets" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    python3 -m pip install -q websockets >/dev/null 2>&1
fi
python3 ksh.py
pkill -f pinggy >/dev/null 2>&1
