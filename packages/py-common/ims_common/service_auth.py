"""Service-to-service authentication (AD-64; LLD 6.8).

Internal endpoints accept only short-lived tokens signed by a known calling service for a
specific audience. Each service signs with its own key; a verifier holds the public keys of
exactly the callers it trusts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import jwt

from ims_common.clock import Clock, SystemClock
from ims_common.tokens import KeySet, TokenCodec, TokenError

SERVICE_TOKEN_TTL = timedelta(seconds=60)
_REFRESH_MARGIN_SECONDS = 15


class ServiceTokenIssuer:
    """Mints and reuses this service's tokens, one per audience."""

    def __init__(self, service_name: str, keys: KeySet, clock: Clock | None = None) -> None:
        self._clock = clock or SystemClock()
        self._codec = TokenCodec(keys, issuer=service_name, clock=self._clock)
        self._service_name = service_name
        self._cache: dict[str, tuple[str, float]] = {}

    def token_for(self, audience: str) -> str:
        cached = self._cache.get(audience)
        now = self._clock.monotonic()
        if cached and cached[1] > now:
            return cached[0]
        token = self._codec.encode(subject=self._service_name, audience=audience, ttl=SERVICE_TOKEN_TTL)
        self._cache[audience] = (token, now + SERVICE_TOKEN_TTL.total_seconds() - _REFRESH_MARGIN_SECONDS)
        return token

    def token_with(self, audience: str, claims: dict[str, Any]) -> str:
        """A fresh token carrying ``claims`` (for example the customer a call is about), so the
        receiver takes them from a verified signature rather than from the request (AD-21)."""
        return self._codec.encode(
            subject=self._service_name, audience=audience, ttl=SERVICE_TOKEN_TTL, claims=claims
        )


@dataclass(frozen=True)
class ServiceCaller:
    name: str
    claims: dict[str, Any] = field(default_factory=dict)


class ServiceTokenVerifier:
    """Accepts tokens for ``audience`` from the listed services only."""

    def __init__(self, audience: str, trusted: dict[str, KeySet], clock: Clock | None = None) -> None:
        self._audience = audience
        self._codecs = {name: TokenCodec(keys, issuer=name, clock=clock) for name, keys in trusted.items()}

    def verify(self, token: str, *, allowed: frozenset[str] | None = None) -> ServiceCaller:
        """Verify against the claimed issuer's keys only. The unverified issuer just selects
        which trusted key set to check; nothing is believed until the signature holds."""
        try:
            claimed = jwt.decode(token, options={"verify_signature": False}).get("iss")
        except jwt.PyJWTError as exc:
            raise TokenError("invalid", "malformed service token") from exc
        codec = self._codecs.get(claimed) if isinstance(claimed, str) else None
        if codec is None or (allowed is not None and claimed not in allowed):
            raise TokenError("invalid", "service is not a trusted caller here")
        claims = codec.decode(token, audience=self._audience)
        if claims["sub"] != claimed:
            raise TokenError("invalid", "service token subject mismatch")
        return ServiceCaller(name=claimed, claims=claims)
