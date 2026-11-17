"""Ed25519 key sets and signed tokens (LLD 6.2, AD-63, AD-64).

A key set holds one current signing key and the public half of the previous one, so rotation
never invalidates tokens that are still within their lifetime ("verifiers accept current and
previous key IDs"). The same key-set type signs JWTs (access, refresh, service tokens) and raw
payloads (snapshot bundles).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal

import jwt
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from ims_common.clock import Clock, SystemClock
from ims_common.ids import uuid7

_ALGORITHM = "EdDSA"
_REQUIRED_CLAIMS = ("iss", "aud", "sub", "iat", "exp", "jti")


class TokenError(Exception):
    """A token failed verification. ``reason`` distinguishes expiry from everything else."""

    def __init__(self, reason: Literal["expired", "invalid"], message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _private_pem(key: Ed25519PrivateKey) -> str:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode("ascii")


def _public_pem(key: Ed25519PublicKey) -> str:
    return key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")


@dataclass(frozen=True)
class KeySet:
    """Signing key (optional) plus every public key a verifier should accept, by key ID."""

    public: dict[str, Ed25519PublicKey]
    current_kid: str | None = None
    private: dict[str, Ed25519PrivateKey] = field(default_factory=dict, repr=False)

    # -- construction -------------------------------------------------------------------------
    @classmethod
    def generate(cls, kid: str) -> KeySet:
        key = Ed25519PrivateKey.generate()
        return cls(public={kid: key.public_key()}, current_kid=kid, private={kid: key})

    @classmethod
    def from_secret(cls, value: dict[str, Any]) -> KeySet:
        public: dict[str, Ed25519PublicKey] = {}
        private: dict[str, Ed25519PrivateKey] = {}
        for kid, entry in value["keys"].items():
            if entry.get("private_pem"):
                loaded = serialization.load_pem_private_key(entry["private_pem"].encode("ascii"), None)
                if not isinstance(loaded, Ed25519PrivateKey):
                    raise ValueError(f"key {kid} is not an Ed25519 private key")
                private[kid] = loaded
                public[kid] = loaded.public_key()
            else:
                loaded_pub = serialization.load_pem_public_key(entry["public_pem"].encode("ascii"))
                if not isinstance(loaded_pub, Ed25519PublicKey):
                    raise ValueError(f"key {kid} is not an Ed25519 public key")
                public[kid] = loaded_pub
        current = value.get("current")
        if current is not None and current not in private:
            raise ValueError("current key has no private half")
        return cls(public=public, current_kid=current, private=private)

    def to_secret(self) -> dict[str, Any]:
        """Full key set, including the private signing key. Store only in the secrets store."""
        keys: dict[str, dict[str, str]] = {}
        for kid, pub in self.public.items():
            entry = {"public_pem": _public_pem(pub)}
            if kid in self.private:
                entry["private_pem"] = _private_pem(self.private[kid])
            keys[kid] = entry
        return {"current": self.current_kid, "keys": keys}

    def public_secret(self) -> dict[str, Any]:
        """Verification-only view: what a peer service needs to check this issuer's signatures."""
        return {
            "current": None,
            "keys": {kid: {"public_pem": _public_pem(p)} for kid, p in self.public.items()},
        }

    def rotated(self, new_kid: str) -> KeySet:
        """New current key; only the outgoing key's public half is kept alongside it."""
        if new_kid in self.public:
            raise ValueError(f"key id already used: {new_kid}")
        key = Ed25519PrivateKey.generate()
        public = {new_kid: key.public_key()}
        if self.current_kid is not None:
            public[self.current_kid] = self.public[self.current_kid]
        return KeySet(public=public, current_kid=new_kid, private={new_kid: key})

    # -- raw payload signatures (snapshot bundles) --------------------------------------------
    def sign(self, payload: bytes) -> tuple[str, bytes]:
        if self.current_kid is None:
            raise RuntimeError("this key set cannot sign: it holds no private key")
        return self.current_kid, self.private[self.current_kid].sign(payload)

    def verify(self, kid: str, payload: bytes, signature: bytes) -> bool:
        key = self.public.get(kid)
        if key is None:
            return False
        try:
            key.verify(signature, payload)
        except InvalidSignature:
            return False
        return True


class TokenCodec:
    """Issues and verifies EdDSA JWTs for one issuer."""

    def __init__(self, keys: KeySet, issuer: str, clock: Clock | None = None) -> None:
        self._keys = keys
        self._issuer = issuer
        self._clock = clock or SystemClock()

    @property
    def issuer(self) -> str:
        return self._issuer

    def encode(
        self,
        *,
        subject: str,
        audience: str,
        ttl: timedelta,
        claims: dict[str, Any] | None = None,
        token_id: str | None = None,
    ) -> str:
        if self._keys.current_kid is None:
            raise RuntimeError("this codec cannot issue tokens: its key set holds no private key")
        now = int(self._clock.now().timestamp())
        payload: dict[str, Any] = dict(claims or {})
        payload.update(
            iss=self._issuer,
            aud=audience,
            sub=subject,
            iat=now,
            exp=now + int(ttl.total_seconds()),
            jti=token_id or str(uuid7()),
        )
        kid = self._keys.current_kid
        return jwt.encode(payload, self._keys.private[kid], algorithm=_ALGORITHM, headers={"kid": kid})

    def decode(self, token: str, *, audience: str) -> dict[str, Any]:
        """Verify signature (by key ID), issuer, audience and lifetime; return the claims."""
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenError("invalid", "malformed token") from exc
        if header.get("alg") != _ALGORITHM:
            raise TokenError("invalid", "unexpected signing algorithm")
        key = self._keys.public.get(header.get("kid", ""))
        if key is None:
            raise TokenError("invalid", "unknown signing key")
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=[_ALGORITHM],
                audience=audience,
                issuer=self._issuer,
                options={
                    "require": list(_REQUIRED_CLAIMS),
                    # Lifetime is checked below against the injected clock.
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                },
            )
        except jwt.PyJWTError as exc:
            raise TokenError("invalid", "token verification failed") from exc
        now = self._clock.now().timestamp()
        if not isinstance(claims["exp"], int) or not isinstance(claims["iat"], int):
            raise TokenError("invalid", "malformed lifetime claims")
        if claims["iat"] > now + 30:
            raise TokenError("invalid", "token issued in the future")
        if now >= claims["exp"]:
            raise TokenError("expired", "token expired")
        return claims


def b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"), validate=True)
