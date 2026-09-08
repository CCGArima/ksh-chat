#!/usr/bin/env python3
"""
===============================================================================
                       KSH CHAT ENGINE v1.1.0
             DEVELOPED & SIGNED BY: KSH DEVELOPMENT TEAM
             REPOSITORY: https://github.com/CCGArima/ksh-chat
-------------------------------------------------------------------------------
MODULE: UNIFIED LAUNCHER & AUTOMATED WAN TUNNEL MANAGER (ksh.py)
===============================================================================
"""

import sys
import os
import socket
import secrets
import asyncio
import argparse
from ui import Colors, render_ksh_logo, generate_join_code, parse_join_code
from server import KSHServer
from client import KSHClient, discover_server


def get_local_ip() -> str:
    """Helper to detect local IP address on LAN."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def auto_start_tunnel(local_port: int = 9999, timeout: float = 10.0) -> tuple:
    """
    Spawns SSH tunnel process in background with real-time stream parsing.
    Tries free.pinggy.io first, then a.pinggy.io as fallback.
    Returns (process_object, external_host, external_port) if successful, else (None, None, None).
    """
    import subprocess
    import re
    import time
    import threading

    print(f"{Colors.YELLOW}[*] Поиск и создание интернет-туннеля (подождите 3-5 сек)...{Colors.RESET}")

    # 1. Cleanup any zombie SSH processes from previous runs
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "ssh.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["pkill", "-f", "pinggy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Ensure an SSH key exists for BatchMode
    key_file = os.path.join(os.path.expanduser("~"), ".ksh_key")
    if not os.path.exists(key_file):
        try:
            subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", key_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def try_endpoint(target_host: str):
        p_cmd = [
            "ssh",
            "-T",
            "-p", "443",
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=3",
        ]
        if os.path.exists(key_file):
            p_cmd.extend(["-i", key_file])
        
        # Windows OpenSSH requires 127.0.0.1 instead of localhost to avoid IPv6 bind failure
        p_cmd.extend(["-R", f"0:127.0.0.1:{local_port}", target_host])

        debug_lines = []
        match_result = []

        try:
            # stdin=PIPE keeps stdin open so Windows OpenSSH doesn't send EOF to remote session channel
            proc = subprocess.Popen(
                p_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                bufsize=0
            )

            def reader():
                try:
                    buf = bytearray()
                    while True:
                        c = proc.stdout.read(1)
                        if not c:
                            if buf:
                                text = buf.decode("utf-8", "ignore").strip()
                                if text: debug_lines.append(text)
                            break
                        buf.extend(c)
                        if c in (b"\n", b"\r", b" "):
                            text = buf.decode("utf-8", "ignore").strip()
                            if text:
                                debug_lines.append(text)
                                m = re.search(r"tcp://([a-zA-Z0-9\.\-]+):(\d{4,5})", text)
                                if m:
                                    match_result.append((m.group(1), int(m.group(2))))
                                    break
                            buf = bytearray()
                        elif len(buf) > 300:
                            text = buf.decode("utf-8", "ignore").strip()
                            if text: debug_lines.append(text)
                            buf = bytearray()
                except Exception:
                    pass

            t = threading.Thread(target=reader, daemon=True)
            t.start()

            start_t = time.time()
            while time.time() - start_t < 7.0:
                if match_result:
                    host, port = match_result[0]
                    return proc, host, port, debug_lines
                if proc.poll() is not None:
                    break
                time.sleep(0.1)

            proc.terminate()
            try: proc.kill()
            except Exception: pass
        except FileNotFoundError:
            print(f"\n{Colors.CRIMSON}[!] ОШИБКА: Команда 'ssh' не найдена в системе.{Colors.RESET}")
            print(f"{Colors.YELLOW}В Windows 10/11 нужно включить 'OpenSSH Client' в дополнительных компонентах.{Colors.RESET}")
            return None, None, None, ["ssh not found"]
        except Exception as e:
            debug_lines.append(str(e))

        return None, None, None, debug_lines

    # Try endpoints
    all_debug = []
    for target in ["tcp@free.pinggy.io", "tcp@a.pinggy.io"]:
        proc, host, ext_port, dlines = try_endpoint(target)
        if host:
            print(f"{Colors.GREEN}[+] Интернет-туннель Pinggy открыт: {host}:{ext_port}{Colors.RESET}")
            return proc, host, ext_port
        all_debug.extend(dlines)

    if all_debug:
        print(f"{Colors.YELLOW}[!] Отладочная информация туннеля:{Colors.RESET}")
        for dline in all_debug[-5:]:
            print(f"    {Colors.DARK_GRAY}{dline}{Colors.RESET}")

    return None, None, None


async def host_auto_room(nick: str, custom_password: str = None, port: int = 9999, external_host: str = None, external_port: int = None):
    """Starts the server in background and connects Host directly to the room."""
    password = custom_password.strip() if custom_password else secrets.token_hex(3).upper()
    
    if external_host and external_port:
        join_code = generate_join_code(external_host, external_port, password, "global")
    else:
        ip = get_local_ip()
        join_code = generate_join_code(ip, port, password, "global")

    srv = KSHServer(host="0.0.0.0", port=port, password=password)
    srv_task = asyncio.create_task(srv.start())

    await asyncio.sleep(0.3)
    
    if srv_task.done() and srv_task.exception():
        import sys
        sys.exit(1)

    client = KSHClient("127.0.0.1", port, "global", nick, password, join_code=join_code)
    await client.start()

    srv_task.cancel()


RENDER_DEFAULT_URL = "wss://ksh-chat.onrender.com"


def interactive_menu():
    print("\033[2J\033[H", end="")  # Clear screen
    print(render_ksh_logo())
    print(f"\n{Colors.BOLD}{Colors.BLOOD_RED} [ KSH PRIVATE CONSOLE CHAT SYSTEM - CLOUD BUILD ]{Colors.RESET}")
    print(f"{Colors.DARK_GRAY} ----------------------------------------------------{Colors.RESET}\n")
    print(f" {Colors.GREEN}[1]{Colors.RESET} {Colors.BOLD}Войти в Облачный KSH Сервер (24/7 Онлайн - БЕЗ КОДОВ){Colors.RESET}")
    print(f" {Colors.CORAL}[2]{Colors.RESET} Создать локальную комнату (LAN / Wi-Fi)")
    print(f" {Colors.CORAL}[3]{Colors.RESET} Создать временную Интернет-комнату (WAN / SSH)")
    print(f" {Colors.CORAL}[4]{Colors.RESET} Присоединиться по коду / адресу (Join Room)")
    print(f" {Colors.CORAL}[5]{Colors.RESET} Выход\n")

    choice = input(f"{Colors.BOLD}{Colors.BLOOD_RED}Выберите вариант [1-5]: {Colors.RESET}").strip()

    if choice == "1":
        print(f"\n{Colors.BOLD}{Colors.WHITE}--- ВХОД В ОБЛАЧНЫЙ СЕРВЕР KSH (24/7 ONLINE) ---{Colors.RESET}")
        nick = input(f" {Colors.CORAL}Ваш никнейм [Operator]: {Colors.RESET}").strip() or "Operator"
        room = input(f" {Colors.CORAL}Имя комнаты [global]: {Colors.RESET}").strip() or "global"
        password = input(f" {Colors.CORAL}Пароль комнаты (Enter - общий доступ): {Colors.RESET}").strip()

        print(f"\n{Colors.GREEN}[+] Подключение к облачному серверу KSH...{Colors.RESET}")
        client = KSHClient(RENDER_DEFAULT_URL, 443, room, nick, password)
        try:
            asyncio.run(client.start())
        except KeyboardInterrupt:
            print(f"\n{Colors.CRIMSON}[!] Сессия завершена.{Colors.RESET}")

    elif choice == "2":
        print(f"\n{Colors.BOLD}{Colors.WHITE}--- СОЗДАНИЕ ЛОКАЛЬНОЙ КОМНАТЫ (LAN) ---{Colors.RESET}")
        nick = input(f" {Colors.CORAL}Ваш никнейм [Host]: {Colors.RESET}").strip() or "Host"
        custom_pass = input(f" {Colors.CORAL}Свой пароль (Enter - сгенерировать случайный): {Colors.RESET}").strip()
        
        print(f"\n{Colors.GREEN}[+] Запуск локального сервера и вход...{Colors.RESET}")
        try:
            asyncio.run(host_auto_room(nick, custom_password=custom_pass if custom_pass else None))
        except KeyboardInterrupt:
            print(f"\n{Colors.CRIMSON}[!] Сервер остановлен.{Colors.RESET}")

    elif choice == "3":
        print(f"\n{Colors.BOLD}{Colors.WHITE}--- СОЗДАНИЕ ИНТЕРНЕТ-КОМНАТЫ (WAN) ---{Colors.RESET}")
        nick = input(f" {Colors.CORAL}Ваш никнейм [Host]: {Colors.RESET}").strip() or "Host"
        custom_pass = input(f" {Colors.CORAL}Свой пароль (Enter - сгенерировать случайный): {Colors.RESET}").strip()

        tunnel_proc, ext_host, ext_port = auto_start_tunnel(9999)

        if not ext_host:
            print(f"{Colors.YELLOW}[!] Авто-туннель не ответил. Введите свой внешний адрес/IP вручную:{Colors.RESET}")
            ext_addr = input(f" {Colors.CORAL}Внешний адрес (например, a.pinggy.link:43210 или IP): {Colors.RESET}").strip()
            if ext_addr:
                if ":" in ext_addr:
                    parts = ext_addr.split(":", 1)
                    ext_host = parts[0].strip()
                    if parts[1].strip().isdigit():
                        ext_port = int(parts[1].strip())
                else:
                    ext_host = ext_addr
                    ext_port = 9999

        print(f"\n{Colors.GREEN}[+] Запуск интернет-сервера и вход...{Colors.RESET}")
        try:
            asyncio.run(host_auto_room(nick, custom_password=custom_pass if custom_pass else None, external_host=ext_host, external_port=ext_port))
        except KeyboardInterrupt:
            print(f"\n{Colors.CRIMSON}[!] Сервер остановлен.{Colors.RESET}")
        finally:
            if tunnel_proc:
                try:
                    tunnel_proc.terminate()
                    tunnel_proc.kill()
                except Exception:
                    pass
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", "ssh.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["pkill", "-f", "pinggy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    elif choice == "4":
        print(f"\n{Colors.BOLD}{Colors.WHITE}--- ПОДКЛЮЧЕНИЕ К КОМНАТЕ ---{Colors.RESET}")
        nick = input(f" {Colors.CORAL}Ваш никнейм [Guest]: {Colors.RESET}").strip() or "Guest"
        raw_code = input(f" {Colors.CORAL}Вставьте КОД подключения KSH-XXXX (или IP:порт / Enter для авто-поиска): {Colors.RESET}").strip()

        if raw_code and raw_code.startswith("KSH-"):
            parsed = parse_join_code(raw_code)
            if parsed:
                host, port, password, room = parsed
                print(f"{Colors.GREEN}[+] Код принят! Подключение к {host}:{port}...{Colors.RESET}")
                client = KSHClient(host, port, room, nick, password, join_code=raw_code)
                try:
                    asyncio.run(client.start())
                except KeyboardInterrupt:
                    print(f"\n{Colors.CRIMSON}[!] Сессия завершена.{Colors.RESET}")
                return
            else:
                print(f"{Colors.RED}[!] Неверный код подключения!{Colors.RESET}")
                return
        elif raw_code:
            host_val, port_val = raw_code, 9999
            if ":" in raw_code:
                parts = raw_code.split(":", 1)
                host_val = parts[0].strip()
                if parts[1].strip().isdigit():
                    port_val = int(parts[1].strip())
            client = KSHClient(host_val, port_val, "global", nick, "")
            try:
                asyncio.run(client.start())
            except KeyboardInterrupt:
                pass
            return
        else:
            client = KSHClient("auto", 9999, "global", nick, "")
            try:
                asyncio.run(client.start())
            except KeyboardInterrupt:
                pass

    else:
        print(f"\n{Colors.CRIMSON}Выход из KSH...{Colors.RESET}")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="KSH Private Console Chat System",
        usage="python ksh.py [mode] [options]"
    )
    subparsers = parser.add_subparsers(dest="mode", help="Mode: client or server")

    server_parser = subparsers.add_parser("server", help="Run KSH Chat Server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host address to bind")
    server_parser.add_argument("--port", type=int, default=9999, help="Port to listen on")
    server_parser.add_argument("--password", default=None, help="Server/Room access password")

    client_parser = subparsers.add_parser("client", help="Run KSH Chat Client")
    client_parser.add_argument("--host", default="auto", help="Server host IP or 'auto' to scan LAN")
    client_parser.add_argument("--port", type=int, default=9999, help="Server port")
    client_parser.add_argument("--room", default="global", help="Room name")
    client_parser.add_argument("--nick", default="Operator", help="Your nickname")
    client_parser.add_argument("--password", default="", help="Room access password")

    args = parser.parse_args()

    if args.mode == "server":
        from server import run_server
        run_server(args.host, args.port, args.password)
    elif args.mode == "client":
        from client import run_client
        run_client(args.host, args.port, args.room, args.nick, args.password)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
