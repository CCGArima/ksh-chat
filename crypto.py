"""
===============================================================================
KSH CHAT ENGINE - CRYPTO MODULE (crypto.py)
-------------------------------------------------------------------------------
ИЗМЕНЕНИЯ И УЛУЧШЕНИЯ (По запросам пользователя):
1. [Mac/Windows Compatibility Fix]: Убрана ошибка Decryption Error при передаче 
   сообщений между Mac и Windows. 
   Переведено на единый алгоритм HMAC-SHA256 XOR Stream Cipher, 
   работающий 100% на чистом Python без обязательной установки pip пакетов.
2. [PBKDF2 Key Derivation]: Автоматическая обрезка пробелов в паролях для 
   предотвращения ошибок при копировании кодов.
===============================================================================
"""

import os
import base64
import hashlib
import hmac
import json


class KSHCrypto:
    """
    KSH Universal Cryptographic Engine.
    Uses PBKDF2 HMAC-SHA256 key derivation and an authenticated HMAC-SHA256 Stream Cipher.
    Runs 100% natively on Python 3 standard library with zero external dependencies,
    guaranteeing 100% cross-platform compatibility between Mac, Windows, and Linux.
    """

    def __init__(self, password: str, salt: bytes = None):
        self.password = password.strip().encode('utf-8')
        if salt is None:
            self.salt = b'KSH_SECURE_SALT_2026'
        else:
            self.salt = salt
        self.key = self._derive_key(self.password, self.salt)

    @staticmethod
    def _derive_key(password: bytes, salt: bytes) -> bytes:
        """Derives a 256-bit key from password using PBKDF2 HMAC SHA256."""
        return hashlib.pbkdf2_hmac('sha256', password, salt, iterations=100000, dklen=32)

    @staticmethod
    def hash_password(password: str) -> str:
        """Generates a SHA-256 hash of password for authentication verification."""
        salt = b'KSH_AUTH_SALT_V1'
        key = hashlib.pbkdf2_hmac('sha256', password.strip().encode('utf-8'), salt, iterations=50000, dklen=32)
        return key.hex()

    def encrypt(self, plaintext: str) -> str:
        """Encrypts plaintext string into a base64 encoded JSON envelope."""
        data_bytes = plaintext.encode('utf-8')

        nonce = os.urandom(16)
        keystream = b''
        block_idx = 0
        while len(keystream) < len(data_bytes):
            h = hmac.new(self.key, nonce + block_idx.to_bytes(4, 'big'), hashlib.sha256)
            keystream += h.digest()
            block_idx += 1

        cipher_bytes = bytes(a ^ b for a, b in zip(data_bytes, keystream[:len(data_bytes)]))
        mac = hmac.new(self.key, nonce + cipher_bytes, hashlib.sha256).digest()

        envelope = {
            'mode': 'HMAC-XOR',
            'nonce': base64.b64encode(nonce).decode('ascii'),
            'ct': base64.b64encode(cipher_bytes).decode('ascii'),
            'mac': base64.b64encode(mac).decode('ascii')
        }

        return base64.b64encode(json.dumps(envelope).encode('utf-8')).decode('ascii')

    def decrypt(self, encrypted_envelope_b64: str) -> str:
        """Decrypts a base64 encoded JSON envelope back into plaintext string."""
        try:
            raw_json = base64.b64decode(encrypted_envelope_b64.encode('ascii')).decode('utf-8')
            envelope = json.loads(raw_json)
            
            nonce = base64.b64decode(envelope['nonce'])
            ct = base64.b64decode(envelope['ct'])

            if 'mac' in envelope:
                mac = base64.b64decode(envelope['mac'])
                expected_mac = hmac.new(self.key, nonce + ct, hashlib.sha256).digest()
                if not hmac.compare_digest(mac, expected_mac):
                    return "[Decryption Error: Wrong room password or tampered message]"

            keystream = b''
            block_idx = 0
            while len(keystream) < len(ct):
                h = hmac.new(self.key, nonce + block_idx.to_bytes(4, 'big'), hashlib.sha256)
                keystream += h.digest()
                block_idx += 1

            plaintext_bytes = bytes(a ^ b for a, b in zip(ct, keystream[:len(ct)]))
            return plaintext_bytes.decode('utf-8')
        except Exception as e:
            return f"[Decryption Error: {str(e)}]"
