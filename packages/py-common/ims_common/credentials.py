"""Password hashing and MFA-secret encryption (AD-65; LLD 6.2, section 16).

``PasswordHasher`` wraps Argon2id and runs it off the event loop. It also holds a dummy hash made
with the same parameters, so a sign-in for an unknown or locked account does the same work as a
wrong password (LD-80). ``verifications`` counts verifications, which tests use to prove that
every sign-in path does exactly one.

``SecretBox`` encrypts TOTP secrets at rest with AES-256-GCM. The ciphertext is bound to the
user it belongs to, so a secret copied onto another user's row does not decrypt.
"""

from __future__ import annotations

import asyncio
import base64
import os
import secrets
from typing import Any

from argon2 import PasswordHasher as Argon2Hasher
from argon2 import Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class PasswordHasher:
    def __init__(self, *, time_cost: int, memory_kib: int, parallelism: int) -> None:
        self._argon = Argon2Hasher(
            time_cost=time_cost,
            memory_cost=memory_kib,
            parallelism=parallelism,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
        self._dummy = self._argon.hash(secrets.token_urlsafe(24))
        self.verifications = 0

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._argon.hash, password)

    async def verify(self, stored_hash: str | None, password: str) -> bool:
        """True if ``password`` matches. A missing hash is checked against the dummy, so the
        caller cannot tell the cases apart by timing."""
        self.verifications += 1
        target = stored_hash or self._dummy

        def _check() -> bool:
            try:
                return self._argon.verify(target, password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False

        matched = await asyncio.to_thread(_check)
        return matched and stored_hash is not None

    async def burn(self, password: str) -> None:
        """Spend one verification on the dummy hash (unknown identifier, locked account)."""
        await self.verify(None, password)

    def needs_rehash(self, stored_hash: str) -> bool:
        try:
            return self._argon.check_needs_rehash(stored_hash)
        except InvalidHashError:
            return True


class SecretBox:
    """AES-256-GCM with a key ring: ``{"current": "k1", "keys": {"k1": "<base64 32 bytes>"}}``."""

    def __init__(self, ring: dict[str, Any]) -> None:
        keys = {kid: base64.b64decode(value, validate=True) for kid, value in ring["keys"].items()}
        if any(len(key) != 32 for key in keys.values()):
            raise ValueError("MFA encryption keys must be 32 bytes")
        if ring["current"] not in keys:
            raise ValueError("current MFA encryption key is missing")
        self._keys = keys
        self._current = ring["current"]

    @staticmethod
    def new_ring(kid: str = "mfa-1") -> dict[str, Any]:
        return {"current": kid, "keys": {kid: base64.b64encode(os.urandom(32)).decode("ascii")}}

    def seal(self, plaintext: bytes, *, context: str) -> tuple[bytes, str]:
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._keys[self._current]).encrypt(nonce, plaintext, context.encode("utf-8"))
        return nonce + ciphertext, self._current

    def open(self, sealed: bytes, *, key_id: str, context: str) -> bytes:
        key = self._keys.get(key_id)
        if key is None:
            raise ValueError("unknown MFA encryption key")
        return AESGCM(key).decrypt(sealed[:12], sealed[12:], context.encode("utf-8"))
