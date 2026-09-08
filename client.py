"""
===============================================================================
                       KSH CHAT ENGINE v1.1.0
             DEVELOPED & SIGNED BY: KSH DEVELOPMENT TEAM
             REPOSITORY: https://github.com/CCGArima/ksh-chat
-------------------------------------------------------------------------------
MODULE: CLIENT INTERACTIVE TUI & HANDSHAKE HANDLER (client.py)
===============================================================================
"""

import sys
import os
import socket
import asyncio
import json
import argparse
from crypto import KSHCrypto
from ui import Colors, render_header, format_message, format_system_banner, parse_join_code


def discover_server(beacon_port: int = 9998, timeout: float = 1.5) -> tuple:
    """
    Sends UDP broadcast to discover active KSH Server on local network.
    Returns (host_ip, port) if found, else None.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)

    try:
        sock.sendto(b"KSH_DISCOVER", ('<broadcast>', beacon_port))
        data, addr = sock.recvfrom(1024)
        info = json.loads(data.decode('utf-8'))
        if info.get("service") == "KSH_CHAT":
            return addr[0], info.get("port", 9999)
    except Exception:
        pass
    finally:
        sock.close()
    return None


class KSHClient:
    def __init__(self, host: str, port: int, room: str, nickname: str, password: str, join_code: str = ""):
        self.host = host
        self.port = port
        self.room = room
        self.nickname = nickname
        self.password = password
        self.join_code = join_code
        self.crypto = KSHCrypto(password) if password else KSHCrypto("DEFAULT_KSH_ROOM_SECRET")
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None
        self.ws = None
        self.is_ws = False
        self.running = True
        self.prompt_prefix = f"{Colors.BOLD}{Colors.BLOOD_RED}[KSH] > {Colors.RESET}"

    async def connect(self) -> bool:
        """Establishes connection and performs authentication handshake."""
        if self.host and self.host.strip().startswith("KSH-"):
            parsed = parse_join_code(self.host)
            if parsed:
                self.host, self.port, self.password, self.room = parsed
                self.join_code = self.host
                self.crypto = KSHCrypto(self.password) if self.password else KSHCrypto("DEFAULT_KSH_ROOM_SECRET")
        elif self.host and ":" in self.host and not self.host.startswith("http") and not self.host.startswith("ws"):
            parts = self.host.split(":", 1)
            if parts[1].strip().isdigit():
                self.host = parts[0].strip()
                self.port = int(parts[1].strip())

        if not self.host or self.host.lower() in ("auto", "scan", "discover"):
            print(f"{Colors.YELLOW}[*] Scanning local network for KSH Server...{Colors.RESET}")
            found = discover_server()
            if found:
                self.host, self.port = found
                print(f"{Colors.GREEN}[+] Server found automatically at {self.host}:{self.port}{Colors.RESET}")
            else:
                print(format_system_banner("DISCOVERY FAILED", "No active KSH server found on local network. Specify Join Code or IP manually."))
                return False

        # Detect WebSocket (Render.com / Amvera / ws / wss)
        if "onrender.com" in self.host or "amvera" in self.host or self.host.startswith("ws://") or self.host.startswith("wss://"):
            self.is_ws = True
            try:
                import websockets
            except ImportError:
                print(format_system_banner("DEPENDENCY MISSING", "WebSocket connection requires 'websockets' package.\nRun: pip install websockets"))
                return False

            ws_url = self.host
            if not ws_url.startswith("ws://") and not ws_url.startswith("wss://"):
                ws_url = f"wss://{self.host}"

            print(f"{Colors.YELLOW}[*] Connecting to cloud WebSocket server: {ws_url}...{Colors.RESET}")
            try:
                import ssl
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
                self.ws = await asyncio.wait_for(websockets.connect(ws_url, ssl=ssl_ctx), timeout=15.0)
            except asyncio.TimeoutError:
                print(format_system_banner("CONNECTION TIMEOUT", f"Cloud server at {ws_url} is waking up or unreachable. Please retry in 20 seconds."))
                return False
            except Exception as e:
                print(format_system_banner("CONNECTION FAILED", f"Could not connect to {ws_url} - {str(e)}"))
                return False

        else:
            try:
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=4.0
                )
            except asyncio.TimeoutError:
                print(format_system_banner("CONNECTION TIMEOUT", f"Could not reach server at {self.host}:{self.port} within 4s.\nMake sure the Server is running on that machine!"))
                return False
            except Exception as e:
                print(format_system_banner("CONNECTION FAILED", f"Could not connect to {self.host}:{self.port} - {str(e)}"))
                return False

        auth_pkt = {
            "type": "AUTH",
            "room": self.room,
            "nick": self.nickname,
            "password_hash": KSHCrypto.hash_password(self.password) if self.password else ""
        }
        await self._send_json(auth_pkt)

        try:
            if self.is_ws:
                line = await asyncio.wait_for(self.ws.recv(), timeout=10.0)
                response = json.loads(line)
            else:
                line = await asyncio.wait_for(self.reader.readline(), timeout=5.0)
                if not line:
                    print(format_system_banner("AUTH ERROR", "Server closed connection during authentication."))
                    return False
                response = json.loads(line.decode('utf-8').strip())

            if response.get("type") == "AUTH_OK":
                self.nickname = response.get("assigned_nick", self.nickname)
                self.room = response.get("room", self.room)
                return True
            else:
                msg = response.get("msg", "Authentication failed.")
                print(format_system_banner("ACCESS DENIED", msg))
                return False

        except Exception as e:
            print(format_system_banner("AUTH ERROR", f"Authentication timeout or error: {str(e)}"))
            return False

    async def _send_json(self, data: dict):
        try:
            if self.is_ws:
                await self.ws.send(json.dumps(data))
            else:
                msg = json.dumps(data) + "\n"
                self.writer.write(msg.encode('utf-8'))
                await self.writer.drain()
        except Exception:
            self.running = False

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        print(render_header(self.room, self.nickname, self.host, self.port, is_e2ee=True, join_code=self.join_code))
        print(f"\n{Colors.DARK_GRAY}--- Type /help for available commands ---{Colors.RESET}\n")

    def print_incoming(self, formatted_str: str):
        """Prints incoming message above current prompt cleanly."""
        sys.stdout.write(f"\r\033[K{formatted_str}\n{self.prompt_prefix}")
        sys.stdout.flush()

    async def receive_loop(self):
        """Asynchronously receives messages from server."""
        while self.running:
            try:
                if self.is_ws:
                    line = await self.ws.recv()
                    data = json.loads(line)
                else:
                    line = await self.reader.readline()
                    if not line:
                        self.print_incoming(format_message("SYSTEM", "Disconnected from server.", is_system=True))
                        self.running = False
                        break
                    try:
                        data = json.loads(line.decode('utf-8').strip())
                    except json.JSONDecodeError:
                        continue

                msg_type = data.get("type")

                if msg_type == "MSG":
                    sender = data.get("sender")
                    encrypted_payload = data.get("payload")
                    decrypted_text = self.crypto.decrypt(encrypted_payload)
                    formatted = format_message(sender, decrypted_text, my_nick=self.nickname)
                    self.print_incoming(formatted)

                elif msg_type == "PM":
                    sender = data.get("sender")
                    encrypted_payload = data.get("payload")
                    decrypted_text = self.crypto.decrypt(encrypted_payload)
                    formatted = format_message(sender, decrypted_text, is_pm=True, my_nick=self.nickname)
                    self.print_incoming(formatted)

                elif msg_type == "PM_ECHO":
                    recipient = data.get("recipient")
                    encrypted_payload = data.get("payload")
                    decrypted_text = self.crypto.decrypt(encrypted_payload)
                    formatted = format_message(f"To {recipient}", decrypted_text, is_pm=True, my_nick=self.nickname)
                    self.print_incoming(formatted)

                elif msg_type == "SYSTEM":
                    msg = data.get("msg")
                    formatted = format_message("SYSTEM", msg, is_system=True)
                    self.print_incoming(formatted)

                elif msg_type == "USER_LIST":
                    users = data.get("users", [])
                    user_str = f"{Colors.BOLD}{Colors.CORAL}Active Users ({len(users)}):{Colors.RESET} " + ", ".join(
                        f"{Colors.BRIGHT_RED}{u}{Colors.RESET}" for u in users
                    )
                    self.print_incoming(user_str)

                elif msg_type == "NICK_CHANGE_OK":
                    self.nickname = data.get("new_nick")
                    self.print_incoming(format_message("SYSTEM", f"Nickname changed to '{self.nickname}'", is_system=True))

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.running:
                    self.print_incoming(format_message("SYSTEM", f"Read error: {e}", is_system=True))
                break

    async def input_loop(self):
        """Asynchronously handles user keyboard input."""
        loop = asyncio.get_event_loop()
        sys.stdout.write(self.prompt_prefix)
        sys.stdout.flush()

        while self.running:
            try:
                user_input = await loop.run_in_executor(None, sys.stdin.readline)
                if not user_input:
                    break

                text = user_input.strip()
                if not text:
                    sys.stdout.write(self.prompt_prefix)
                    sys.stdout.flush()
                    continue

                if text.startswith("/"):
                    await self._handle_command(text)
                else:
                    encrypted_payload = self.crypto.encrypt(text)
                    await self._send_json({
                        "type": "MSG",
                        "payload": encrypted_payload
                    })

                if self.running:
                    sys.stdout.write(self.prompt_prefix)
                    sys.stdout.flush()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"\nInput error: {e}")
                break

    async def _handle_command(self, cmd_line: str):
        parts = cmd_line.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("/quit", "/exit"):
            self.running = False
            print(f"\n{Colors.CRIMSON}[!] Leaving KSH Chat...{Colors.RESET}")
            if self.writer:
                self.writer.close()

        elif cmd == "/help":
            help_text = (
                f"\n{Colors.BOLD}{Colors.BLOOD_RED}═══ KSH CHAT COMMANDS ═══{Colors.RESET}\n"
                f" {Colors.CORAL}/users{Colors.RESET}             - List active users in room\n"
                f" {Colors.CORAL}/pm <nick> <msg>{Colors.RESET}   - Send private encrypted message\n"
                f" {Colors.CORAL}/nick <new_name>{Colors.RESET}  - Change your nickname\n"
                f" {Colors.CORAL}/clear{Colors.RESET}             - Clear screen and reload header\n"
                f" {Colors.CORAL}/help{Colors.RESET}              - Show this help menu\n"
                f" {Colors.CORAL}/quit{Colors.RESET}              - Exit chat\n"
            )
            print(f"\r\033[K{help_text}")

        elif cmd == "/clear":
            self.clear_screen()

        elif cmd == "/users":
            await self._send_json({"type": "USERS"})

        elif cmd == "/nick":
            if args:
                await self._send_json({"type": "NICK", "new_nick": args.strip()})
            else:
                print(f"\r\033[K{Colors.YELLOW}Usage: /nick <new_name>{Colors.RESET}")

        elif cmd == "/pm":
            pm_parts = args.split(maxsplit=1)
            if len(pm_parts) == 2:
                recipient, pm_msg = pm_parts[0], pm_parts[1]
                encrypted_payload = self.crypto.encrypt(pm_msg)
                await self._send_json({
                    "type": "PM",
                    "recipient": recipient,
                    "payload": encrypted_payload
                })
            else:
                print(f"\r\033[K{Colors.YELLOW}Usage: /pm <nickname> <message>{Colors.RESET}")

        else:
            print(f"\r\033[K{Colors.YELLOW}Unknown command '{cmd}'. Type /help for assistance.{Colors.RESET}")

    async def start(self):
        if not await self.connect():
            return

        self.clear_screen()
        rx_task = asyncio.create_task(self.receive_loop())
        tx_task = asyncio.create_task(self.input_loop())

        done, pending = await asyncio.wait(
            [rx_task, tx_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()

        if self.writer:
            self.writer.close()
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass


def run_client(host: str, port: int, room: str, nick: str, password: str, join_code: str = ""):
    client = KSHClient(host, port, room, nick, password, join_code=join_code)
    try:
        asyncio.run(client.start())
    except KeyboardInterrupt:
        print(f"\n{Colors.CRIMSON}[!] Session closed.{Colors.RESET}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KSH Private Chat Client")
    parser.add_argument("--host", default="auto", help="Server host IP, Join Code, or 'auto' to scan LAN")
    parser.add_argument("--port", type=int, default=9999, help="Server port")
    parser.add_argument("--room", default="global", help="Room name")
    parser.add_argument("--nick", default="Operator", help="Your nickname")
    parser.add_argument("--password", default="", help="Room access password")
    parser.add_argument("--code", default="", help="Join Code")
    args = parser.parse_args()

    run_client(args.host, args.port, args.room, args.nick, args.password, join_code=args.code)
