"""Symmetric encryption for OAuth tokens stored in the database (used by publishing in Phase 5)."""

from cryptography.fernet import Fernet, InvalidToken


class TokenCipher:
    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError("TOKEN_ENCRYPTION_KEY is not set (see .env.example for how to generate one)")
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Could not decrypt token: wrong TOKEN_ENCRYPTION_KEY?") from exc
