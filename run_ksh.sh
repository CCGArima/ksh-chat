#!/usr/bin/env bash
# KSH Chat Launcher for Linux & macOS
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"
python3 -c "import websockets" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    python3 -m pip install -q websockets >/dev/null 2>&1
fi
python3 ksh.py
