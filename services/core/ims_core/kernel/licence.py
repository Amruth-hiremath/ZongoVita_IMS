"""Licence state gate (AD-24, AD-25, AD-78; LLD 6.4).

Every request and job passes the gate. It never calls the Registry per request: each process
keeps a snapshot per customer, refreshed after 60 seconds and when the change feed reports a
change. Validity dates are evaluated locally, so grace and read-only start on time.

A platform fault never blocks a known customer. If the Registry cannot be reached, the last
snapshot held for the customer is honoured whatever its age, and the on-call alarm is raised.
A process that started during the outage, and so holds nothing, loads the latest signed
snapshot bundle from object storage. Only a customer with no snapshot anywhere is refused
(503 LICENCE_UNVERIFIABLE). A customer the Registry positively does not know is refused.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import httpx

from ims_common.clock import Clock
from ims_common.objectstore import ObjectNotFoundError, ObjectStore
from ims_common.problem import DomainError
from ims_common.service_auth import ServiceTokenIssuer
from ims_common.snapshot_bundle import BUNDLE_OBJECT_KEY, BundleVerificationError, unseal
from ims_common.tokens import KeySet
from ims_contracts.enums import ChangeType
from ims_contracts.errors import ErrorCode
from ims_contracts.licence import LicenceSnapshot, LicenceState, derive_state
from ims_contracts.platform_api import (
    SERVICE_AUDIENCE_PLATFORM_INTERNAL,
    ChangeFeedEntry,
    ChangesResponse,
    SnapshotBundle,
)

log = logging.getLogger("ims.licence")

ALARM_REGISTRY_UNREACHABLE = "registry_unreachable"
ALARM_BUNDLE_INVALID = "snapshot_bundle_invalid"


class RegistryUnavailableError(Exception):
    """The Registry did not give a usable answer (network error, timeout, 5xx, refused)."""


class CustomerUnknownError(Exception):
    """The Registry answered: this customer is unknown or was never licensed."""


class RegistryClient(Protocol):
    async def fetch_snapshot(self, customer_id: UUID) -> LicenceSnapshot: ...

    async def fetch_changes(self, after_seq: int | None) -> ChangesResponse: ...


class HttpRegistryClient:
    """Calls the Platform Service's internal interface with this service's signed token."""

    def __init__(self, http: httpx.AsyncClient, tokens: ServiceTokenIssuer, *, retries: int = 2) -> None:
        self._http = http
        self._tokens = tokens
        self._retries = retries

    async def _get(self, path: str, params: dict[str, int] | None = None) -> httpx.Response:
        for _attempt in range(self._retries + 1):
            try:
                token = self._tokens.token_for(SERVICE_AUDIENCE_PLATFORM_INTERNAL)
                response = await self._http.get(
                    path, params=params, headers={"Authorization": f"Bearer {token}"}
                )
            except httpx.HTTPError:
                continue
            # Only a clean 200 or a well-formed 404 is an answer. Anything else (5xx, a proxy
            # error page, a rejected service token) is a platform fault, never a verdict.
            if response.status_code in (200, 404):
                return response
        raise RegistryUnavailableError(path)

    async def fetch_snapshot(self, customer_id: UUID) -> LicenceSnapshot:
        response = await self._get(f"/internal/v1/customers/{customer_id}/snapshot")
        try:
            body = response.json()
        except ValueError as exc:
            raise RegistryUnavailableError("unparseable snapshot response") from exc
        if response.status_code == 404:
            if isinstance(body, dict) and body.get("code") == ErrorCode.NOT_FOUND:
                raise CustomerUnknownError(str(customer_id))
            raise RegistryUnavailableError("unexpected 404 from the Registry")
        try:
            return LicenceSnapshot.model_validate(body)
        except ValueError as exc:
            raise RegistryUnavailableError("snapshot does not match the contract") from exc

    async def fetch_changes(self, after_seq: int | None) -> ChangesResponse:
        response = await self._get(
            "/internal/v1/changes", None if after_seq is None else {"after_seq": after_seq}
        )
        if response.status_code != 200:
            raise RegistryUnavailableError("change feed unavailable")
        try:
            return ChangesResponse.model_validate(response.json())
        except ValueError as exc:
            raise RegistryUnavailableError("change feed does not match the contract") from exc


class BundleSource:
    """Loads and verifies the signed snapshot bundle (LD-78)."""

    def __init__(self, store: ObjectStore, verification_keys: KeySet) -> None:
        self._store = store
        self._keys = verification_keys

    async def load(self) -> SnapshotBundle | None:
        try:
            data = await self._store.get(BUNDLE_OBJECT_KEY)
        except ObjectNotFoundError:
            return None
        except Exception:
            log.exception("snapshot bundle could not be read", extra={"alarm": ALARM_BUNDLE_INVALID})
            return None
        try:
            return unseal(data, self._keys)
        except BundleVerificationError:
            # An unverifiable bundle is never used: without a valid signature it proves nothing.
            log.critical("snapshot bundle failed verification", extra={"alarm": ALARM_BUNDLE_INVALID})
            return None


@dataclass
class _Entry:
    snapshot: LicenceSnapshot
    refreshed_at: float
    #: Set by the change feed: refresh on next use, but keep as last known-good meanwhile.
    stale: bool = False


ChangeListener = Callable[[ChangeFeedEntry], None]


class SnapshotStore:
    """Per-process licence snapshots with last known-good semantics."""

    def __init__(
        self,
        client: RegistryClient,
        clock: Clock,
        *,
        ttl_seconds: float = 60.0,
        probe_backoff_seconds: float = 5.0,
        bundle: BundleSource | None = None,
        bundle_cache_seconds: float = 60.0,
    ) -> None:
        self._client = client
        self._clock = clock
        self._ttl = ttl_seconds
        self._probe_backoff = probe_backoff_seconds
        self._bundle_source = bundle
        self._bundle_cache_seconds = bundle_cache_seconds
        self._entries: dict[UUID, _Entry] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}
        self._registry_down = False
        self._next_probe_at = 0.0
        self._probing = False
        self._bundle: dict[UUID, LicenceSnapshot] | None = None
        self._bundle_loaded_at: float | None = None
        self._feed_position: int | None = None
        self._listeners: list[ChangeListener] = []

    # ---------------------------------------------------------------------------- telemetry
    @property
    def registry_reachable(self) -> bool:
        return not self._registry_down

    def snapshot_age_seconds(self, customer_id: UUID) -> float | None:
        entry = self._entries.get(customer_id)
        return None if entry is None else max(0.0, self._clock.monotonic() - entry.refreshed_at)

    def add_change_listener(self, listener: ChangeListener) -> None:
        """Other caches (login directory, credentials) evict on Registry changes too."""
        self._listeners.append(listener)

    # ------------------------------------------------------------------------------- outage
    def _mark_down(self) -> None:
        self._next_probe_at = self._clock.monotonic() + self._probe_backoff
        if not self._registry_down:
            self._registry_down = True
            # This is the signal on-call is paged on (HLD section 10, observability).
            log.critical(
                "Licence Registry unreachable; honouring last known-good snapshots",
                extra={"alarm": ALARM_REGISTRY_UNREACHABLE},
            )

    def _mark_up(self) -> None:
        if self._registry_down:
            self._registry_down = False
            log.warning("Licence Registry reachable again", extra={"alarm": ALARM_REGISTRY_UNREACHABLE})

    def _may_call_registry(self) -> bool:
        """While the Registry is down only one caller at a time probes it, and only after the
        back-off; every other request is served from last known-good without waiting."""
        if not self._registry_down:
            return True
        return not self._probing and self._clock.monotonic() >= self._next_probe_at

    # -------------------------------------------------------------------------------- reads
    def _fresh(self, entry: _Entry | None) -> bool:
        return (
            entry is not None and not entry.stale and self._clock.monotonic() - entry.refreshed_at < self._ttl
        )

    async def get(self, customer_id: UUID) -> LicenceSnapshot:
        """Current snapshot, refreshed if due; last known-good if the Registry is unreachable.

        Raises CustomerUnknownError if the Registry says the customer is unknown or unlicensed,
        and DomainError(LICENCE_UNVERIFIABLE) if no snapshot was ever held and none can be had.
        """
        entry = self._entries.get(customer_id)
        if self._fresh(entry):
            return entry.snapshot  # type: ignore[union-attr]
        lock = self._locks.setdefault(customer_id, asyncio.Lock())
        async with lock:
            entry = self._entries.get(customer_id)
            if self._fresh(entry):
                return entry.snapshot  # type: ignore[union-attr]
            if not self._may_call_registry():
                return await self._last_known_good(customer_id, entry)
            probing = self._registry_down
            if probing:
                self._probing = True
            try:
                snapshot = await self._client.fetch_snapshot(customer_id)
            except CustomerUnknownError:
                self._mark_up()
                self._entries.pop(customer_id, None)
                raise
            except RegistryUnavailableError:
                self._mark_down()
                return await self._last_known_good(customer_id, entry)
            finally:
                if probing:
                    self._probing = False
            self._mark_up()
            self._entries[customer_id] = _Entry(snapshot, self._clock.monotonic())
            return snapshot

    async def _last_known_good(self, customer_id: UUID, entry: _Entry | None) -> LicenceSnapshot:
        if entry is not None:
            return entry.snapshot  # any age: there is no maximum staleness
        snapshot = (await self._bundle_snapshots()).get(customer_id)
        if snapshot is None:
            raise DomainError(
                ErrorCode.LICENCE_UNVERIFIABLE,
                headers={"Retry-After": str(max(1, int(self._probe_backoff)))},
            )
        # Marked stale so it is replaced as soon as the Registry answers again.
        self._entries[customer_id] = _Entry(snapshot, self._clock.monotonic(), stale=True)
        return snapshot

    async def _bundle_snapshots(self) -> dict[UUID, LicenceSnapshot]:
        if self._bundle_source is None:
            return {}
        now = self._clock.monotonic()
        if (
            self._bundle is None
            or self._bundle_loaded_at is None
            or now - self._bundle_loaded_at >= self._bundle_cache_seconds
        ):
            bundle = await self._bundle_source.load()
            self._bundle = {s.customer_id: s for s in bundle.snapshots} if bundle else {}
            self._bundle_loaded_at = now
        return self._bundle

    # -------------------------------------------------------------------------- change feed
    def _apply_change(self, change: ChangeFeedEntry) -> None:
        entry = self._entries.get(change.customer_id)
        # A snapshot read at or after this change already reflects it.
        if (
            entry is not None
            and entry.snapshot.feed_seq < change.seq
            and change.change_type is not ChangeType.DIRECTORY
        ):
            entry.stale = True
        for listener in self._listeners:
            try:
                listener(change)
            except Exception:
                log.exception("change listener failed", extra={"feed_seq": change.seq})

    async def poll_changes_once(self) -> int:
        """Read the change feed from the last position and mark changed customers stale.

        Returns the number of changes applied. The 60-second refresh covers any notice missed
        while the Registry was unreachable.
        """
        applied = 0
        try:
            if self._feed_position is None:
                self._feed_position = (await self._client.fetch_changes(None)).head_seq
                self._mark_up()
                return 0
            while True:
                page = await self._client.fetch_changes(self._feed_position)
                self._mark_up()
                for change in page.entries:
                    self._apply_change(change)
                    self._feed_position = change.seq
                    applied += 1
                if not page.entries or self._feed_position >= page.head_seq:
                    return applied
        except RegistryUnavailableError:
            self._mark_down()
            return applied

    async def run_change_feed(self, poll_seconds: float) -> None:
        """Poll the change feed until cancelled (every 10 seconds; LLD 6.4)."""
        while True:
            try:
                await self.poll_changes_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("change feed poll failed")
            await asyncio.sleep(poll_seconds)


class LicenceGate:
    """Step 4 of the request pipeline, and the same check for jobs."""

    def __init__(self, store: SnapshotStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    async def check(
        self, customer_id: UUID, *, module: str, read_only_ok: bool
    ) -> tuple[LicenceSnapshot, LicenceState]:
        try:
            snapshot = await self._store.get(customer_id)
        except CustomerUnknownError:
            # The credential names a customer the Registry does not license: not a usable login.
            raise DomainError(ErrorCode.AUTH_REQUIRED) from None
        state = derive_state(snapshot, self._clock.now())
        if state is LicenceState.TERMINATED:
            raise DomainError(ErrorCode.LICENCE_TERMINATED)
        if state is LicenceState.SUSPENDED:
            raise DomainError(ErrorCode.LICENCE_SUSPENDED)
        if state is LicenceState.READ_ONLY and not read_only_ok:
            raise DomainError(ErrorCode.LICENCE_READ_ONLY)
        if module not in snapshot.modules:
            raise DomainError(ErrorCode.MODULE_NOT_LICENSED)
        return snapshot, state
