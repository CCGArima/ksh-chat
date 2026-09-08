#!/usr/bin/env python3
"""
===============================================================================
KSH CHAT ENGINE - UNIFIED LAUNCHER (ksh.py)
-------------------------------------------------------------------------------
ИЗМЕНЕНИЯ И УЛУЧШЕНИЯ:
1. [Автоматическое создание комнаты]: При выборе пункта 1 программа сама 
   запускает сервер и сразу подключает вас в чат под вашим ником.
2. [Постоянный или случайный код]: Добавлен выбор: нажмите Enter для рандомного 
   кода или введите свой постоянный пароль.
3. [Код подключения KSH-XXXX]: Авто-генерация единой ссылки/кода подключения 
   для друзей.
4. [Подключение в 1 клик]: При выборе пункта 2 друг просто вставляет 
   Код Подключения.
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

    client = KSHClient("127.0.0.1", port, "global", nick, password, join_code=join_code)
    await client.start()

    srv_task.cancel()


def interactive_menu():
    print("\033[2J\033[H", end="")  # Clear screen
    print(render_ksh_logo())
    print(f"\n{Colors.BOLD}{Colors.BLOOD_RED} [ KSH PRIVATE CONSOLE CHAT SYSTEM ]{Colors.RESET}")
    print(f"{Colors.DARK_GRAY} ----------------------------------------{Colors.RESET}\n")
    print(f" {Colors.CORAL}[1]{Colors.RESET} Создать локальную комнату (LAN / Wi-Fi)")
    print(f" {Colors.CORAL}[2]{Colors.RESET} Создать Интернет-комнату (WAN / Global)")
    print(f" {Colors.CORAL}[3]{Colors.RESET} Присоединиться по коду (Join Room)")
    print(f" {Colors.CORAL}[4]{Colors.RESET} Выход\n")

    choice = input(f"{Colors.BOLD}{Colors.BLOOD_RED}Выберите вариант [1-4]: {Colors.RESET}").strip()

    if choice == "1":
        print(f"\n{Colors.BOLD}{Colors.WHITE}--- СОЗДАНИЕ ЛОКАЛЬНОЙ КОМНАТЫ (LAN) ---{Colors.RESET}")
        nick = input(f" {Colors.CORAL}Ваш никнейм [Host]: {Colors.RESET}").strip() or "Host"
        custom_pass = input(f" {Colors.CORAL}Свой пароль (Enter - сгенерировать случайный): {Colors.RESET}").strip()
        
        print(f"\n{Colors.GREEN}[+] Запуск локального сервера и вход...{Colors.RESET}")
        try:
            asyncio.run(host_auto_room(nick, custom_password=custom_pass if custom_pass else None))
        except KeyboardInterrupt:
            print(f"\n{Colors.CRIMSON}[!] Сервер остановлен.{Colors.RESET}")

    elif choice == "2":
        print(f"\n{Colors.BOLD}{Colors.WHITE}--- СОЗДАНИЕ ИНТЕРНЕТ-КОМНАТЫ (WAN) ---{Colors.RESET}")
        print(f"{Colors.DARK_GRAY} Для подключения друзей вне вашего дома требуется внешний IP или Pinggy/Ngrok туннель.{Colors.RESET}")
        print(f"{Colors.YELLOW} Команда для запуска бесплатного туннеля в другом терминале:{Colors.RESET}")
        print(f"   {Colors.BOLD}ssh -p 443 -R 0:localhost:9999 a.pinggy.io{Colors.RESET}\n")
        
        nick = input(f" {Colors.CORAL}Ваш никнейм [Host]: {Colors.RESET}").strip() or "Host"
        ext_addr = input(f" {Colors.CORAL}Внешний адрес/туннель (например, a.pinggy.link:43210 или ваш Публичный IP): {Colors.RESET}").strip()
        custom_pass = input(f" {Colors.CORAL}Свой пароль (Enter - сгенерировать случайный): {Colors.RESET}").strip()

        ext_host, ext_port = None, None
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

    elif choice == "3":
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
