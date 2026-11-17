"""Login identifiers and their keyed hashes (LD-10; LLD 4, 6.3).

The Login Directory never stores an identifier, only keyed hashes of its normalised form:

* ``login_hash = HMAC-SHA256(pepper, identifier)`` is the directory's key. The pepper is known
  only to the Platform Service (LD-10).
* ``lookup_hash = HMAC-SHA256(directory lookup key, identifier)`` lets a product resolve an
  identifier from the signed snapshot bundle while the Platform Service is unreachable (AD-79,
  LLD 6.3), without the product ever holding the pepper. See Implementation_Progress.md, D-13.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import unicodedata
from typing import Any

MAX_IDENTIFIER_LENGTH = 254
MIN_KEY_BYTES = 32


class InvalidIdentifierError(ValueError):
    """The value cannot be a login identifier."""


def normalise_login_identifier(raw: str) -> str:
    """Trim, Unicode NFKC, lower case (LLD section 4). Rejects empty, overlong or control text."""
    if not isinstance(raw, str):
        raise InvalidIdentifierError("login identifier must be text")
    value = unicodedata.normalize("NFKC", raw).strip().lower()
    if not value:
        raise InvalidIdentifierError("login identifier is empty")
    if len(value) > MAX_IDENTIFIER_LENGTH:
        raise InvalidIdentifierError("login identifier is too long")
    if any(unicodedata.category(ch).startswith("C") or ch.isspace() for ch in value):
        raise InvalidIdentifierError("login identifier contains spaces or control characters")
    return value


def keyed_hash(key: bytes, identifier: str) -> bytes:
    """HMAC-SHA256 of the normalised identifier; 32 bytes."""
    if len(key) < MIN_KEY_BYTES:
        raise ValueError("hash key is too short")
    return hmac.new(key, normalise_login_identifier(identifier).encode("utf-8"), hashlib.sha256).digest()


def key_from_secret(secret: dict[str, Any]) -> bytes:
    """Decode a ``{"key": "<base64>"}`` secret into key bytes, checking its length."""
    key = base64.b64decode(secret["key"], validate=True)
    if len(key) < MIN_KEY_BYTES:
        raise ValueError("key secret holds fewer than 32 bytes")
    return key


def new_key_secret() -> dict[str, str]:
    """A fresh random 32-byte key in the secret format above (provisioning and tests)."""
    import secrets  # noqa: PLC0415 - only needed when generating

    return {"key": base64.b64encode(secrets.token_bytes(MIN_KEY_BYTES)).decode("ascii")}
