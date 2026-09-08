"""
===============================================================================
KSH CHAT ENGINE - SERVER MODULE (server.py)
-------------------------------------------------------------------------------
ИЗМЕНЕНИЯ И УЛУЧШЕНИЯ (По запросам пользователя):
1. [UDP Beacon Auto-Discovery]: Добавлен асинхронный UDP-радиомаяк на порту 9998 
   для автоматического обнаружения сервера в локальной сети.
2. [Multi-Room & E2E Payload Routing]: Безопасная асинхронная маршрутизация 
   зашифрованных сообщений, личных сообщений (/pm) и комнат.
===============================================================================
"""

import asyncio
import json
import logging
import argparse
from typing import Dict, Set
from crypto import KSHCrypto
from ui import Colors, render_ksh_logo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class KSHBeaconProtocol(asyncio.DatagramProtocol):
    """UDP Beacon listener for auto-discovery of KSH Server on local network."""
    def __init__(self, tcp_port: int):
        self.tcp_port = tcp_port

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr):
        if data.strip() == b"KSH_DISCOVER":
            response = json.dumps({
                "service": "KSH_CHAT",
                "port": self.tcp_port
            }).encode('utf-8')
            self.transport.sendto(response, addr)


class KSHClientHandler:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, server):
        self.reader = reader
        self.writer = writer
        self.server = server
        self.nick = "Anonymous"
        self.room = "global"
        self.authenticated = False
        self.addr = writer.get_extra_info('peername')

    async def send_json(self, data: dict):
        try:
            message = json.dumps(data) + "\n"
            self.writer.write(message.encode('utf-8'))
            await self.writer.drain()
        except Exception:
            pass

    async def handle(self):
        logging.info(f"New connection from {self.addr}")
        try:
            while True:
                line = await self.reader.readline()
                if not line:
                    break

                try:
                    data = json.loads(line.decode('utf-8').strip())
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                if msg_type == "AUTH":
                    await self._handle_auth(data)
                elif not self.authenticated:
                    await self.send_json({"type": "ERROR", "msg": "Authentication required."})
                    break
                elif msg_type == "MSG":
                    await self._handle_msg(data)
                elif msg_type == "PM":
                    await self._handle_pm(data)
                elif msg_type == "NICK":
                    await self._handle_nick(data)
                elif msg_type == "USERS":
                    await self._handle_users()
                elif msg_type == "PING":
                    await self.send_json({"type": "PONG"})

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Error handling client {self.addr}: {e}")
        finally:
            await self._cleanup()

    async def _handle_auth(self, data: dict):
        room = data.get("room", "global").strip()
        pass_hash = data.get("password_hash", "")
        nick = data.get("nick", "Guest").strip()

        expected_hash = self.server.get_room_password_hash(room)
        if expected_hash and pass_hash != expected_hash:
            logging.warning(f"Auth failed for {self.addr} in room '{room}'")
            await self.send_json({"type": "AUTH_FAIL", "msg": "Invalid room password!"})
            self.writer.close()
            return

        unique_nick = self.server.make_unique_nick(room, nick)
        self.nick = unique_nick
        self.room = room
        self.authenticated = True

        self.server.add_client(self)
        logging.info(f"User '{self.nick}' authenticated in room '{self.room}' from {self.addr}")

        await self.send_json({
            "type": "AUTH_OK",
            "assigned_nick": self.nick,
            "room": self.room
        })

        await self.server.broadcast_system(self.room, f"User '{self.nick}' joined room '{self.room}'")

    async def _handle_msg(self, data: dict):
        payload = data.get("payload")
        if payload:
            await self.server.broadcast_room(self.room, {
                "type": "MSG",
                "sender": self.nick,
                "payload": payload
            })

    async def _handle_pm(self, data: dict):
        recipient = data.get("recipient")
        payload = data.get("payload")
        if recipient and payload:
            target_client = self.server.get_client_by_nick(self.room, recipient)
            if target_client:
                await target_client.send_json({
                    "type": "PM",
                    "sender": self.nick,
                    "payload": payload
                })
                await self.send_json({
                    "type": "PM_ECHO",
                    "recipient": recipient,
                    "payload": payload
                })
            else:
                await self.send_json({
                    "type": "SYSTEM",
                    "msg": f"User '{recipient}' not found in room '{self.room}'."
                })

    async def _handle_nick(self, data: dict):
        new_nick = data.get("new_nick", "").strip()
        if not new_nick or len(new_nick) > 20:
            await self.send_json({"type": "SYSTEM", "msg": "Invalid nickname length."})
            return

        old_nick = self.nick
        unique_nick = self.server.make_unique_nick(self.room, new_nick)
        self.nick = unique_nick

        await self.send_json({"type": "NICK_CHANGE_OK", "new_nick": self.nick})
        await self.server.broadcast_system(self.room, f"'{old_nick}' is now known as '{self.nick}'")

    async def _handle_users(self):
        user_list = self.server.get_room_users(self.room)
        await self.send_json({
            "type": "USER_LIST",
            "users": user_list
        })

    async def _cleanup(self):
        if self.authenticated:
            self.server.remove_client(self)
            logging.info(f"User '{self.nick}' disconnected from room '{self.room}'")
            await self.server.broadcast_system(self.room, f"User '{self.nick}' left the chat.")
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass


class KSHServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 9999, password: str = None, beacon_port: int = 9998):
        self.host = host
        self.port = port
        self.password = password
        self.beacon_port = beacon_port
        self.password_hash = KSHCrypto.hash_password(password) if password else None
        self.rooms: Dict[str, Set[KSHClientHandler]] = {}

    def get_room_password_hash(self, room: str) -> str:
        return self.password_hash

    def add_client(self, client: KSHClientHandler):
        if client.room not in self.rooms:
            self.rooms[client.room] = set()
        self.rooms[client.room].add(client)

    def remove_client(self, client: KSHClientHandler):
        if client.room in self.rooms and client in self.rooms[client.room]:
            self.rooms[client.room].remove(client)
            if not self.rooms[client.room]:
                del self.rooms[client.room]

    def make_unique_nick(self, room: str, base_nick: str) -> str:
        existing = {c.nick for c in self.rooms.get(room, set())}
        if base_nick not in existing:
            return base_nick
        idx = 1
        while f"{base_nick}_{idx}" in existing:
            idx += 1
        return f"{base_nick}_{idx}"

    def get_room_users(self, room: str) -> list:
        return [c.nick for c in self.rooms.get(room, set())]

    def get_client_by_nick(self, room: str, nick: str) -> KSHClientHandler:
        for client in self.rooms.get(room, set()):
            if client.nick.lower() == nick.lower():
                return client
        return None

    async def broadcast_room(self, room: str, data: dict, exclude: KSHClientHandler = None):
        clients = list(self.rooms.get(room, set()))
        for client in clients:
            if client != exclude:
                await client.send_json(data)

    async def broadcast_system(self, room: str, message: str):
        await self.broadcast_room(room, {
            "type": "SYSTEM",
            "msg": message
        })

    async def start(self):
        loop = asyncio.get_running_loop()
        
        server = await asyncio.start_server(
            lambda r, w: KSHClientHandler(r, w, self).handle(),
            self.host, self.port
        )

        try:
            await loop.create_datagram_endpoint(
                lambda: KSHBeaconProtocol(self.port),
                local_addr=("0.0.0.0", self.beacon_port)
            )
            beacon_status = f"{Colors.GREEN}ONLINE (Port {self.beacon_port}){Colors.RESET}"
        except Exception:
            beacon_status = f"{Colors.YELLOW}OFFLINE (Port busy){Colors.RESET}"

        print("\n" + render_ksh_logo())
        print(f"\n{Colors.BOLD}{Colors.BLOOD_RED}[KSH PRIVATE CHAT SERVER INITIALIZED]{Colors.RESET}")
        print(f"{Colors.WHITE} Listening on:{Colors.RESET} {Colors.CORAL}{self.host}:{self.port}{Colors.RESET}")
        print(f"{Colors.WHITE} Protection:{Colors.RESET}   {Colors.GREEN if self.password else Colors.YELLOW}{'PASSWORD PROTECTED' if self.password else 'OPEN (NO PASSWORD)'}{Colors.RESET}")
        print(f"{Colors.WHITE} Auto-Discovery:{Colors.RESET} {beacon_status}")
        print(f"{Colors.WHITE} Protocol:{Colors.RESET}     {Colors.BRIGHT_RED}KSH TCP + E2E CIPHER{Colors.RESET}\n")

        async with server:
            await server.serve_forever()


def run_server(host: str = "0.0.0.0", port: int = 9999, password: str = None):
    srv = KSHServer(host=host, port=port, password=password)
    try:
        asyncio.run(srv.start())
    except KeyboardInterrupt:
        print(f"\n{Colors.CRIMSON}[!] Server shutting down...{Colors.RESET}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KSH Private Chat Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind")
    parser.add_argument("--port", type=int, default=9999, help="Server port")
    parser.add_argument("--password", default=None, help="Room / Server access password")
    args = parser.parse_args()

    run_server(args.host, args.port, args.password)
