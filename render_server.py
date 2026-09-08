#!/usr/bin/env python3
"""
===============================================================================
                       KSH CHAT ENGINE v1.1.0
             DEVELOPED & SIGNED BY: KSH DEVELOPMENT TEAM
             REPOSITORY: https://github.com/CCGArima/ksh-chat
-------------------------------------------------------------------------------
MODULE: CLOUD WEBSOCKET SERVER FOR RENDER.COM / AMVERA (render_server.py)
===============================================================================
"""

import os
import sys
import json
import http
import asyncio
import logging
from typing import Dict, Set

try:
    import websockets
except ImportError:
    print("[!] Error: 'websockets' package is required. Run: pip install websockets")
    sys.exit(1)

from crypto import KSHCrypto
from ui import Colors, render_ksh_logo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class KSHWebSocketClientHandler:
    def __init__(self, ws, server):
        self.ws = ws
        self.server = server
        self.nick = "Anonymous"
        self.room = "global"
        self.authenticated = False
        self.remote_address = getattr(ws, "remote_address", ("unknown", 0))

    async def send_json(self, data: dict):
        try:
            await self.ws.send(json.dumps(data))
        except Exception:
            pass

    async def handle(self):
        logging.info(f"New WebSocket client from {self.remote_address}")
        try:
            async for raw_message in self.ws:
                try:
                    data = json.loads(raw_message)
                except Exception:
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

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logging.error(f"Error handling client {self.remote_address}: {e}")
        finally:
            await self._cleanup()

    async def _handle_auth(self, data: dict):
        room = data.get("room", "global").strip()
        pass_hash = data.get("password_hash", "")
        nick = data.get("nick", "Guest").strip()

        expected_hash = self.server.get_room_password_hash(room)
        if expected_hash and pass_hash != expected_hash:
            logging.warning(f"Auth failed for {self.remote_address} in room '{room}'")
            await self.send_json({"type": "AUTH_FAIL", "msg": "Invalid room password!"})
            await self.ws.close()
            return

        unique_nick = self.server.make_unique_nick(room, nick)
        self.nick = unique_nick
        self.room = room
        self.authenticated = True

        self.server.add_client(self)
        logging.info(f"User '{self.nick}' authenticated in room '{self.room}' from {self.remote_address}")

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
            await self.ws.close()
        except Exception:
            pass


class KSHCloudServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 10000, password: str = None):
        self.host = host
        self.port = port
        self.password = password
        self.password_hash = KSHCrypto.hash_password(password) if password else None
        self.rooms: Dict[str, Set[KSHWebSocketClientHandler]] = {}

    def get_room_password_hash(self, room: str) -> str:
        return self.password_hash

    def add_client(self, client: KSHWebSocketClientHandler):
        if client.room not in self.rooms:
            self.rooms[client.room] = set()
        self.rooms[client.room].add(client)

    def remove_client(self, client: KSHWebSocketClientHandler):
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

    def get_client_by_nick(self, room: str, nick: str) -> KSHWebSocketClientHandler:
        for client in self.rooms.get(room, set()):
            if client.nick.lower() == nick.lower():
                return client
        return None

    async def broadcast_room(self, room: str, data: dict, exclude: KSHWebSocketClientHandler = None):
        clients = list(self.rooms.get(room, set()))
        for client in clients:
            if client != exclude:
                await client.send_json(data)

    async def broadcast_system(self, room: str, message: str):
        await self.broadcast_room(room, {
            "type": "SYSTEM",
            "msg": message
        })

    def process_http_request(self, connection, request):
        """Responds to Render.com HTTP health checks with HTTP 200 only for non-WebSocket HTTP requests."""
        upgrade = request.headers.get("Upgrade", "").lower()
        if upgrade != "websocket" and request.path in ("/", "/health", "/status"):
            return connection.respond(http.HTTPStatus.OK, "KSH PRIVATE CHAT CLOUD SERVER IS RUNNING OK\n")
        return None

    async def start(self):
        print("\n" + render_ksh_logo())
        print(f"\n{Colors.BOLD}{Colors.BLOOD_RED}[KSH CLOUD WEBSOCKET SERVER INITIALIZED]{Colors.RESET}")
        print(f"{Colors.WHITE} Listening on:{Colors.RESET} {Colors.CORAL}{self.host}:{self.port}{Colors.RESET}")
        print(f"{Colors.WHITE} Protocol:{Colors.RESET}     {Colors.BRIGHT_RED}WSS / WEBSOCKET + E2E CIPHER{Colors.RESET}\n")

        async with websockets.serve(
            lambda ws: KSHWebSocketClientHandler(ws, self).handle(),
            self.host,
            self.port,
            process_request=self.process_http_request
        ):
            await asyncio.Future()  # run forever


def main():
    port = int(os.environ.get("PORT", 10000))
    password = os.environ.get("KSH_PASSWORD", None)
    server = KSHCloudServer(host="0.0.0.0", port=port, password=password)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("[!] Server shutting down...")


if __name__ == "__main__":
    main()
