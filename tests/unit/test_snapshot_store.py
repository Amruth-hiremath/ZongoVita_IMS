"""Licence snapshot cache and last known-good behaviour (AD-24, AD-25; LLD 6.4).

Uses an in-memory Registry so every call and every outage is observable and deterministic.
The same behaviour is exercised end to end against the real Platform Service in tests/kernel.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from ims_common.clock import ManualClock
from ims_common.ids import uuid7
from ims_common.objectstore import FileObjectStore
from ims_common.problem import DomainError
from ims_common.snapshot_bundle import BUNDLE_CONTENT_TYPE, BUNDLE_OBJECT_KEY, seal
from ims_common.tokens import KeySet
from ims_contracts.enums import ChangeType, CustomerStatus
from ims_contracts.errors import ErrorCode
from ims_contracts.licence import LicenceSnapshot, LicenceState
from ims_contracts.platform_api import ChangeFeedEntry, ChangesResponse, SnapshotBundle
from ims_core.kernel.licence import (
    ALARM_REGISTRY_UNREACHABLE,
    BundleSource,
    CustomerUnknownError,
    LicenceGate,
    RegistryUnavailableError,
    SnapshotStore,
)
from tests.unit.test_licence_state import snapshot as make_snapshot

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


class FakeRegistry:
    def __init__(self) -> None:
        self.snapshots: dict[UUID, LicenceSnapshot] = {}
        self.feed: list[ChangeFeedEntry] = []
        self.down = False
        self.snapshot_calls = 0
        self.change_calls = 0

    def put(self, snap: LicenceSnapshot, change: ChangeType | None = None) -> LicenceSnapshot:
        """Store a snapshot as the Registry would after a committed change."""
        seq = len(self.feed)
        if change is not None:
            seq += 1
            self.feed.append(
                ChangeFeedEntry(seq=seq, customer_id=snap.customer_id, change_type=change, changed_at=NOW)
            )
        stored = snap.model_copy(update={"feed_seq": seq})
        self.snapshots[snap.customer_id] = stored
        return stored

    async def fetch_snapshot(self, customer_id: UUID) -> LicenceSnapshot:
        self.snapshot_calls += 1
        if self.down:
            raise RegistryUnavailableError("down")
        try:
            return self.snapshots[customer_id].model_copy(update={"feed_seq": len(self.feed)})
        except KeyError:
            raise CustomerUnknownError(str(customer_id)) from None

    async def fetch_changes(self, after_seq: int | None) -> ChangesResponse:
        self.change_calls += 1
        if self.down:
            raise RegistryUnavailableError("down")
        entries = [] if after_seq is None else [e for e in self.feed if e.seq > after_seq]
        return ChangesResponse(entries=entries, head_seq=len(self.feed))


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(NOW)


@pytest.fixture
def registry() -> FakeRegistry:
    return FakeRegistry()


@pytest.fixture
def store(registry: FakeRegistry, clock: ManualClock) -> SnapshotStore:
    return SnapshotStore(registry, clock, ttl_seconds=60, probe_backoff_seconds=5)


def _active(valid_days: int = 30) -> LicenceSnapshot:
    return make_snapshot().model_copy(
        update={"customer_id": uuid7(), "valid_until": NOW + timedelta(days=valid_days), "fetched_at": NOW}
    )


async def test_snapshot_is_cached_for_the_ttl_then_refreshed(
    registry: FakeRegistry, store: SnapshotStore, clock: ManualClock
) -> None:
    snap = registry.put(_active())
    for _ in range(50):
        await store.get(snap.customer_id)
    assert registry.snapshot_calls == 1, "no Registry call per request"
    clock.advance(seconds=59)
    await store.get(snap.customer_id)
    assert registry.snapshot_calls == 1
    clock.advance(seconds=1)
    await store.get(snap.customer_id)
    assert registry.snapshot_calls == 2


async def test_change_notice_refreshes_before_the_ttl(
    registry: FakeRegistry, store: SnapshotStore, clock: ManualClock
) -> None:
    snap = registry.put(_active())
    await store.poll_changes_once()  # a new process starts listening at the feed head
    assert (await store.get(snap.customer_id)).customer_status is CustomerStatus.ACTIVE

    registry.put(snap.model_copy(update={"customer_status": CustomerStatus.SUSPENDED}), ChangeType.STATUS)
    clock.advance(seconds=10)
    assert (await store.get(snap.customer_id)).customer_status is CustomerStatus.ACTIVE, "not yet notified"
    assert await store.poll_changes_once() == 1
    assert (await store.get(snap.customer_id)).customer_status is CustomerStatus.SUSPENDED
    assert registry.snapshot_calls == 2


async def test_missed_notice_is_covered_by_the_ttl_refresh(
    registry: FakeRegistry, store: SnapshotStore, clock: ManualClock
) -> None:
    snap = registry.put(_active())
    await store.get(snap.customer_id)
    registry.snapshots[snap.customer_id] = snap.model_copy(
        update={"customer_status": CustomerStatus.SUSPENDED}
    )
    clock.advance(seconds=60)  # the change notice never arrived
    assert (await store.get(snap.customer_id)).customer_status is CustomerStatus.SUSPENDED


async def test_notice_already_reflected_in_the_snapshot_does_not_refetch(
    registry: FakeRegistry, store: SnapshotStore
) -> None:
    await store.poll_changes_once()
    snap = registry.put(_active(), ChangeType.LICENCE)  # change committed before we first read
    await store.get(snap.customer_id)
    assert await store.poll_changes_once() == 1
    await store.get(snap.customer_id)
    assert registry.snapshot_calls == 1


async def test_directory_changes_do_not_invalidate_snapshots_but_reach_listeners(
    registry: FakeRegistry, store: SnapshotStore
) -> None:
    seen: list[ChangeFeedEntry] = []
    store.add_change_listener(seen.append)
    await store.poll_changes_once()
    snap = registry.put(_active())
    await store.get(snap.customer_id)
    registry.put(snap, ChangeType.DIRECTORY)
    await store.poll_changes_once()
    await store.get(snap.customer_id)
    assert registry.snapshot_calls == 1
    assert [c.change_type for c in seen] == [ChangeType.DIRECTORY]


async def test_registry_outage_honours_last_known_good_at_any_age(
    registry: FakeRegistry,
    store: SnapshotStore,
    clock: ManualClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    snap = registry.put(_active())
    await store.get(snap.customer_id)
    registry.down = True
    with caplog.at_level(logging.WARNING, logger="ims.licence"):
        for days in (0.001, 1, 30, 400):
            clock.advance(days=days)
            assert (await store.get(snap.customer_id)).customer_id == snap.customer_id
    assert not store.registry_reachable
    alarms = [r for r in caplog.records if getattr(r, "alarm", None) == ALARM_REGISTRY_UNREACHABLE]
    assert [r.levelno for r in alarms] == [logging.CRITICAL], "on-call is paged once per outage"


async def test_outage_does_not_put_a_registry_call_on_every_request(
    registry: FakeRegistry, store: SnapshotStore, clock: ManualClock
) -> None:
    snaps = [registry.put(_active()) for _ in range(20)]
    for snap in snaps:
        await store.get(snap.customer_id)
    registry.down = True
    clock.advance(seconds=61)
    calls_before = registry.snapshot_calls
    for _ in range(10):
        for snap in snaps:
            await store.get(snap.customer_id)
    assert registry.snapshot_calls == calls_before + 1, "one failed call opens the breaker for everyone"
    clock.advance(seconds=5)  # back-off elapsed: exactly one probe
    for snap in snaps:
        await store.get(snap.customer_id)
    assert registry.snapshot_calls == calls_before + 2


async def test_recovery_resumes_refreshing(
    registry: FakeRegistry, store: SnapshotStore, clock: ManualClock
) -> None:
    snap = registry.put(_active())
    await store.get(snap.customer_id)
    registry.down = True
    clock.advance(seconds=61)
    await store.get(snap.customer_id)
    registry.snapshots[snap.customer_id] = snap.model_copy(
        update={"customer_status": CustomerStatus.SUSPENDED}
    )
    registry.down = False
    assert (await store.get(snap.customer_id)).customer_status is CustomerStatus.ACTIVE, (
        "still inside back-off"
    )
    clock.advance(seconds=5)
    assert (await store.get(snap.customer_id)).customer_status is CustomerStatus.SUSPENDED
    assert store.registry_reachable


async def test_change_feed_poll_also_detects_outage_and_recovery(
    registry: FakeRegistry, store: SnapshotStore
) -> None:
    await store.poll_changes_once()
    registry.down = True
    assert await store.poll_changes_once() == 0
    assert not store.registry_reachable
    registry.down = False
    await store.poll_changes_once()
    assert store.registry_reachable


async def test_unknown_customer_is_refused_and_forgotten(
    registry: FakeRegistry, store: SnapshotStore, clock: ManualClock
) -> None:
    with pytest.raises(CustomerUnknownError):
        await store.get(uuid7())
    snap = registry.put(_active())
    await store.get(snap.customer_id)
    del registry.snapshots[snap.customer_id]
    clock.advance(seconds=60)
    with pytest.raises(CustomerUnknownError):
        await store.get(snap.customer_id)
    registry.down = True  # no last known-good is kept for a customer the Registry disowned
    clock.advance(seconds=60)
    with pytest.raises(DomainError) as excinfo:
        await store.get(snap.customer_id)
    assert excinfo.value.code is ErrorCode.LICENCE_UNVERIFIABLE


async def test_never_seen_customer_during_outage_is_unverifiable(
    registry: FakeRegistry, store: SnapshotStore
) -> None:
    snap = registry.put(_active())
    registry.down = True
    with pytest.raises(DomainError) as excinfo:
        await store.get(snap.customer_id)
    assert (excinfo.value.status, excinfo.value.code) == (503, ErrorCode.LICENCE_UNVERIFIABLE)
    assert "Retry-After" in excinfo.value.headers


async def test_cold_start_during_outage_uses_the_signed_bundle(
    registry: FakeRegistry, clock: ManualClock, tmp_path
) -> None:
    keys = KeySet.generate("b1")
    objects = FileObjectStore(tmp_path)
    known = registry.put(_active())
    bundle = SnapshotBundle(generated_at=NOW, feed_seq=0, snapshots=[known], directory=[])
    await objects.put(BUNDLE_OBJECT_KEY, seal(bundle, keys), content_type=BUNDLE_CONTENT_TYPE)

    registry.down = True
    store = SnapshotStore(
        registry,
        clock,
        ttl_seconds=60,
        probe_backoff_seconds=5,
        bundle=BundleSource(objects, KeySet.from_secret(keys.public_secret())),
    )
    assert (await store.get(known.customer_id)).customer_code == known.customer_code
    # A customer absent from the bundle was never licensed as far as this process can tell.
    with pytest.raises(DomainError) as excinfo:
        await store.get(uuid7())
    assert excinfo.value.code is ErrorCode.LICENCE_UNVERIFIABLE

    # Once the Registry answers again the bundle copy is replaced by the live snapshot.
    registry.snapshots[known.customer_id] = known.model_copy(update={"max_users": 999})
    registry.down = False
    clock.advance(seconds=5)
    assert (await store.get(known.customer_id)).max_users == 999


async def test_forged_bundle_is_never_used(registry: FakeRegistry, clock: ManualClock, tmp_path) -> None:
    objects = FileObjectStore(tmp_path)
    known = registry.put(_active())
    forged = SnapshotBundle(generated_at=NOW, feed_seq=0, snapshots=[known], directory=[])
    await objects.put(
        BUNDLE_OBJECT_KEY, seal(forged, KeySet.generate("b1")), content_type=BUNDLE_CONTENT_TYPE
    )
    registry.down = True
    store = SnapshotStore(registry, clock, bundle=BundleSource(objects, KeySet.generate("b1")))
    with pytest.raises(DomainError) as excinfo:
        await store.get(known.customer_id)
    assert excinfo.value.code is ErrorCode.LICENCE_UNVERIFIABLE


# ------------------------------------------------------------------------------------- gate
async def test_gate_decisions(registry: FakeRegistry, store: SnapshotStore, clock: ManualClock) -> None:
    gate = LicenceGate(store, clock)
    snap = registry.put(_active(valid_days=10).model_copy(update={"modules": frozenset({"ims.core"})}))
    cid = snap.customer_id

    async def check(module: str = "ims.core", read_only_ok: bool = False) -> LicenceState:
        return (await gate.check(cid, module=module, read_only_ok=read_only_ok))[1]

    async def refused(module: str = "ims.core", read_only_ok: bool = False) -> ErrorCode:
        with pytest.raises(DomainError) as excinfo:
            await gate.check(cid, module=module, read_only_ok=read_only_ok)
        assert excinfo.value.status == 403
        return excinfo.value.code

    assert await check() is LicenceState.ACTIVE
    assert await refused(module="ims.replenishment") is ErrorCode.MODULE_NOT_LICENSED

    clock.advance(days=10)  # end date reached: grace starts on time, full access
    assert await check() is LicenceState.GRACE
    clock.advance(days=14)  # grace over: read-only
    assert await refused() is ErrorCode.LICENCE_READ_ONLY
    assert await check(read_only_ok=True) is LicenceState.READ_ONLY
    # The module check still applies to routes that are allowed in read-only state.
    assert await refused(module="ims.replenishment", read_only_ok=True) is ErrorCode.MODULE_NOT_LICENSED

    registry.put(snap.model_copy(update={"customer_status": CustomerStatus.SUSPENDED}))
    clock.advance(seconds=60)
    assert await refused(read_only_ok=True) is ErrorCode.LICENCE_SUSPENDED
    registry.put(snap.model_copy(update={"customer_status": CustomerStatus.TERMINATED}))
    clock.advance(seconds=60)
    assert await refused(read_only_ok=True) is ErrorCode.LICENCE_TERMINATED


async def test_gate_refuses_a_customer_the_registry_does_not_license(
    store: SnapshotStore, clock: ManualClock
) -> None:
    with pytest.raises(DomainError) as excinfo:
        await LicenceGate(store, clock).check(uuid7(), module="ims.core", read_only_ok=True)
    assert (excinfo.value.status, excinfo.value.code) == (401, ErrorCode.AUTH_REQUIRED)


async def test_grace_and_read_only_start_on_time_during_an_outage(
    registry: FakeRegistry, store: SnapshotStore, clock: ManualClock
) -> None:
    """Dates are evaluated locally, so expiry does not wait for the Registry."""
    gate = LicenceGate(store, clock)
    snap = registry.put(_active(valid_days=1))
    assert (await gate.check(snap.customer_id, module="ims.core", read_only_ok=False))[
        1
    ] is LicenceState.ACTIVE
    registry.down = True
    clock.advance(days=1)
    assert (await gate.check(snap.customer_id, module="ims.core", read_only_ok=False))[
        1
    ] is LicenceState.GRACE
    clock.advance(days=14)
    with pytest.raises(DomainError) as excinfo:
        await gate.check(snap.customer_id, module="ims.core", read_only_ok=False)
    assert excinfo.value.code is ErrorCode.LICENCE_READ_ONLY
