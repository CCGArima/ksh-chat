import unittest
import asyncio
import json
from crypto import KSHCrypto
from ui import render_ksh_logo, render_header, format_message, strip_ansi
from server import KSHServer
from client import KSHClient


class TestKSHCrypto(unittest.TestCase):
    def test_encryption_decryption(self):
        password = "secret_room_key_123"
        crypto1 = KSHCrypto(password)
        crypto2 = KSHCrypto(password)

        msg = "Привет, это секретное сообщение!"
        encrypted = crypto1.encrypt(msg)
        self.assertNotEqual(msg, encrypted)

        decrypted = crypto2.decrypt(encrypted)
        self.assertEqual(msg, decrypted)

    def test_wrong_password_decryption(self):
        crypto1 = KSHCrypto("correct_pass")
        crypto2 = KSHCrypto("wrong_pass")

        msg = "Top secret data"
        encrypted = crypto1.encrypt(msg)
        decrypted = crypto2.decrypt(encrypted)

        self.assertTrue("Decryption Error" in decrypted or decrypted != msg)


class TestKSHUI(unittest.TestCase):
    def test_logo_render(self):
        logo = render_ksh_logo()
        plain_logo = strip_ansi(logo)
        self.assertIn("██╗", plain_logo)

    def test_header_render(self):
        header = render_header("test-room", "Alice", "127.0.0.1", 9999)
        plain_header = strip_ansi(header)
        self.assertIn("ROOM:", plain_header)
        self.assertIn("test-room", plain_header)
        self.assertIn("Alice", plain_header)

    def test_message_formatting(self):
        formatted = format_message("Alice", "Hello World", my_nick="Bob")
        self.assertIn("Alice", strip_ansi(formatted))
        self.assertIn("Hello World", strip_ansi(formatted))


class TestKSHServerClientIntegration(unittest.TestCase):
    def test_server_client_handshake(self):
        async def run_test():
            # Start server
            server = KSHServer(host="127.0.0.1", port=19999, password="testpassword")
            srv_task = asyncio.create_task(server.start())

            await asyncio.sleep(0.2)

            # Test client auth failure with wrong password
            client_wrong = KSHClient("127.0.0.1", 19999, "global", "Hacker", "wrongpass")
            auth_ok = await client_wrong.connect()
            self.assertFalse(auth_ok)

            # Test client auth success
            client_right = KSHClient("127.0.0.1", 19999, "global", "Operator1", "testpassword")
            auth_ok2 = await client_right.connect()
            self.assertTrue(auth_ok2)

            if client_right.writer:
                client_right.writer.close()

            srv_task.cancel()
            try:
                await srv_task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
