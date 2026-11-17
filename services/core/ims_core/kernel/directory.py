"""Login Directory client and cache (AD-20, AD-79; LLD 6.3, 6.8).

Sign-in must find the customer before it can check a password, and must not depend on the
Platform Service being up (AD-79). Each process therefore caches resolved identifiers for ten
minutes, keyed by the lookup hash (never the identifier itself), and evicts them when the change
feed reports a directory change for their customer. If the Platform Service is unreachable, a
cached entry is used whatever its age, and an uncached identifier is resolved from the signed
snapshot bundle.

Unknown identifiers are cached too, so unknown and known identifiers cost the same lookups; any
directory change clears them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import httpx

from ims_common.clock import Clock
from ims_common.identifiers import InvalidIdentifierError, keyed_hash, normalise_login_identifier
from ims_common.problem import DomainError
from ims_common.service_auth import ServiceTokenIssuer
from ims_contracts.enums import ChangeType, PrincipalType
from ims_contracts.errors import ErrorCode
from ims_contracts.platform_api import (
    SERVICE_AUDIENCE_PLATFORM_INTERNAL,
    ChangeFeedEntry,
    DirectoryEntry,
    DirectoryReservationResponse,
)
from ims_core.kernel.licence import BundleSource, RegistryUnavailableError

log = logging.getLogger("ims.directory")


class DirectoryClient(Protocol):
    async def resolve(self, identifier: str) -> DirectoryEntry | None: ...

    async def reserve(
        self, *, customer_id: UUID, principal_type: PrincipalType, principal_id: UUID, identifier: str
    ) -> DirectoryReservationResponse: ...

    async def activate(
        self, *, customer_id: UUID, principal_type: PrincipalType, principal_id: UUID, identifier: str
    ) -> None: ...

    async def disable(
        self, *, customer_id: UUID, principal_type: PrincipalType, principal_id: UUID
    ) -> None: ...


class HttpDirectoryClient:
    """The Platform Service's directory endpoints, called with this service's signed token."""

    def __init__(self, http: httpx.AsyncClient, tokens: ServiceTokenIssuer, *, retries: int = 2) -> None:
        self._http = http
        self._tokens = tokens
        self._retries = retries

    async def _post(self, path: str, body: dict[str, Any], *, answers: frozenset[int]) -> httpx.Response:
        """POST with retries. Only the listed statuses are answers; anything else (network error,
        5xx, a rejected service token) is a platform fault."""
        for _attempt in range(self._retries + 1):
            try:
                token = self._tokens.token_for(SERVICE_AUDIENCE_PLATFORM_INTERNAL)
                response = await self._http.post(
                    path, json=body, headers={"Authorization": f"Bearer {token}"}
                )
            except httpx.HTTPError:
                continue
            if response.status_code in answers:
                return response
            if response.status_code < 500:
                break
        raise RegistryUnavailableError(path)

    @staticmethod
    def _code(response: httpx.Response) -> str | None:
        try:
            body = response.json()
        except ValueError:
            return None
        return body.get("code") if isinstance(body, dict) else None

    async def resolve(self, identifier: str) -> DirectoryEntry | None:
        response = await self._post(
            "/internal/v1/directory/resolve", {"identifier": identifier}, answers=frozenset({200, 404})
        )
        if response.status_code == 404:
            if self._code(response) != ErrorCode.NOT_FOUND:
                raise RegistryUnavailableError("unexpected 404 from the directory")
            return None
        try:
            return DirectoryEntry.model_validate(response.json())
        except ValueError as exc:
            raise RegistryUnavailableError("directory entry does not match the contract") from exc

    async def reserve(
        self, *, customer_id: UUID, principal_type: PrincipalType, principal_id: UUID, identifier: str
    ) -> DirectoryReservationResponse:
        response = await self._post(
            "/internal/v1/directory/reservations",
            {
                "customer_id": str(customer_id),
                "principal_type": principal_type.value,
                "principal_id": str(principal_id),
                "identifier": identifier,
            },
            answers=frozenset({201, 409}),
        )
        if response.status_code == 409:
            raise DomainError(ErrorCode.LOGIN_IDENTIFIER_TAKEN)
        return DirectoryReservationResponse.model_validate(response.json())

    async def activate(
        self, *, customer_id: UUID, principal_type: PrincipalType, principal_id: UUID, identifier: str
    ) -> None:
        response = await self._post(
            f"/internal/v1/directory/{principal_id}/activate",
            {
                "customer_id": str(customer_id),
                "principal_type": principal_type.value,
                "identifier": identifier,
            },
            answers=frozenset({204, 409}),
        )
        if response.status_code == 409:
            code = self._code(response)
            raise DomainError(
                ErrorCode.LOGIN_IDENTIFIER_TAKEN
                if code == ErrorCode.LOGIN_IDENTIFIER_TAKEN
                else ErrorCode.INVALID_STATE_TRANSITION
            )

    async def disable(self, *, customer_id: UUID, principal_type: PrincipalType, principal_id: UUID) -> None:
        await self._post(
            f"/internal/v1/directory/{principal_id}/disable",
            {"customer_id": str(customer_id), "principal_type": principal_type.value},
            answers=frozenset({204}),
        )


@dataclass
class _Cached:
    entry: DirectoryEntry | None  # None: the identifier is not in the directory
    stored_at: float


class DirectoryCache:
    def __init__(
        self,
        client: DirectoryClient,
        *,
        lookup_key: bytes,
        clock: Clock,
        ttl_seconds: float = 600.0,
        probe_backoff_seconds: float = 5.0,
        bundle: BundleSource | None = None,
        bundle_cache_seconds: float = 60.0,
    ) -> None:
        self._client = client
        self._lookup_key = lookup_key
        self._clock = clock
        self._ttl = ttl_seconds
        self._probe_backoff = probe_backoff_seconds
        self._bundle_source = bundle
        self._bundle_cache_seconds = bundle_cache_seconds
        self._entries: dict[bytes, _Cached] = {}
        self._unreachable_until = 0.0
        self._bundle: dict[str, DirectoryEntry] | None = None
        self._bundle_loaded_at: float | None = None

    @property
    def client(self) -> DirectoryClient:
        return self._client

    async def resolve(self, identifier: str) -> DirectoryEntry | None:
        """Customer and principal of an identifier, or None. Never raises for a platform fault."""
        try:
            normalised = normalise_login_identifier(identifier)
        except InvalidIdentifierError:
            return None
        key = keyed_hash(self._lookup_key, normalised)
        cached = self._entries.get(key)
        now = self._clock.monotonic()
        if cached is not None and now - cached.stored_at < self._ttl:
            return cached.entry
        if now >= self._unreachable_until:
            try:
                entry = await self._client.resolve(normalised)
            except RegistryUnavailableError:
                self._unreachable_until = now + self._probe_backoff
                log.warning("Login Directory unreachable; using cached entries and the snapshot bundle")
            else:
                self._entries[key] = _Cached(entry, now)
                return entry
        if cached is not None:
            return cached.entry  # last known-good, any age
        return (await self._bundle_entries()).get(key.hex())

    async def _bundle_entries(self) -> dict[str, DirectoryEntry]:
        if self._bundle_source is None:
            return {}
        now = self._clock.monotonic()
        if (
            self._bundle is None
            or self._bundle_loaded_at is None
            or now - self._bundle_loaded_at >= self._bundle_cache_seconds
        ):
            bundle = await self._bundle_source.load()
            entries: dict[str, DirectoryEntry] = {}
            for item in bundle.directory if bundle else []:
                try:
                    entries[item.lookup_hash] = DirectoryEntry(
                        customer_id=item.customer_id,
                        principal_type=item.principal_type,  # type: ignore[arg-type]
                        principal_id=item.principal_id,
                        status=item.status,  # type: ignore[arg-type]
                    )
                except ValueError:
                    continue
            self._bundle, self._bundle_loaded_at = entries, now
        return self._bundle

    def forget(self, identifier: str) -> None:
        """Drop one identifier, after this process changed its entry."""
        try:
            self._entries.pop(keyed_hash(self._lookup_key, identifier), None)
        except InvalidIdentifierError:
            return

    def on_change(self, change: ChangeFeedEntry) -> None:
        """Change-feed listener: a directory change evicts that customer's entries and every
        cached "unknown" (the identifier may now exist)."""
        if change.change_type is not ChangeType.DIRECTORY:
            return
        self._entries = {
            key: cached
            for key, cached in self._entries.items()
            if cached.entry is not None and cached.entry.customer_id != change.customer_id
        }
