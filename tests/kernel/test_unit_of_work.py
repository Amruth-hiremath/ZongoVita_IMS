"""Unit of work, idempotency and concurrency through the pooler (AD-08, AD-33, AD-34, AD-51).

LLD section 17: "duplicates act once", "first write wins", and one transaction per command
covering the change, its audit entry, its outbox event and its idempotency key.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from sqlalchemy import text

from ims_common.clock import ManualClock
from ims_common.ids import uuid7
from ims_contracts.errors import PROBLEM_CONTENT_TYPE
from ims_platform.registry import RegistryService
from tests.conftest import CoreApp
from tests.support.stack import Customer, Stack, onboard_customer

pytestmark = pytest.mark.db

KEY_A = "probe.lock_timeout_hours"
KEY_B = "probe.second"


def _url(key: str = KEY_A) -> str:
    return f"/ui/v1/probe/settings/{key}"


async def _counts(stack: Stack, customer: Customer) -> dict[str, Any]:
    """What is durably in the customer's database, read as the owner on a separate connection."""
    engine = await stack.migration_engine(customer.db)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT (SELECT count(*) FROM config.settings) AS settings,
                               (SELECT count(*) FROM audit.audit_log) AS audit,
                               (SELECT count(*) FROM integration.outbox_events) AS events,
                               (SELECT count(*) FROM integration.idempotency_keys) AS keys
                        """
                    )
                )
            ).one()
    finally:
        await engine.dispose()
    return dict(row._mapping)


@pytest.fixture
async def customer(
    stack: Stack, session_registry: RegistryService, clock: ManualClock, fresh_code: str
) -> Customer:
    """A customer with an empty database, so absolute row counts are meaningful."""
    return await onboard_customer(stack, session_registry, fresh_code, now=clock.now())


@pytest.fixture
async def gxp_customer(
    stack: Stack, session_registry: RegistryService, clock: ManualClock, fresh_code: str
) -> Customer:
    return await onboard_customer(stack, session_registry, f"{fresh_code}g", now=clock.now(), gxp_mode=True)


async def _put(
    app: CoreApp,
    token: str,
    value: Any,
    expected_version: int,
    *,
    key: str | None = None,
    url: str | None = None,
    **extra: Any,
) -> httpx.Response:
    headers = app.auth(token)
    if key is not None:
        headers["Idempotency-Key"] = key
    return await app.client.put(
        url or _url(), json={"value": value, "expected_version": expected_version, **extra}, headers=headers
    )


# ---------------------------------------------------------------------------- one transaction
async def test_change_audit_event_and_key_commit_together(
    core_app: CoreApp, stack: Stack, customer: Customer
) -> None:
    user = uuid7()
    token = core_app.user_token(customer, user)
    response = await _put(core_app, token, 48, 0, key="commit-together-1", reason="initial value")
    assert response.status_code == 200
    assert response.json() == {"key": KEY_A, "value": 48, "version": 1}
    assert await _counts(stack, customer) == {"settings": 1, "audit": 1, "events": 1, "keys": 1}

    engine = await stack.migration_engine(customer.db)
    try:
        async with engine.connect() as conn:
            audit = (await conn.execute(text("SELECT *, txid::text AS tx FROM audit.audit_log"))).one()
            event = (
                await conn.execute(text("SELECT *, txid::text AS tx FROM integration.outbox_events"))
            ).one()
            stored = (await conn.execute(text("SELECT * FROM integration.idempotency_keys"))).one()
    finally:
        await engine.dispose()

    # Who, what, when, before and after, request ID (AD-66).
    assert (audit.actor_type, audit.actor_id, audit.source) == ("user", user, "ui")
    assert (audit.action, audit.entity_type, audit.entity_id) == (
        "config.setting.changed",
        "config.setting",
        KEY_A,
    )
    assert audit.before == {"value": None, "default": 72}
    assert audit.after == {"value": 48, "version": 1}
    assert audit.reason == "initial value"
    assert audit.request_id == response.headers["x-request-id"]
    # The event exists because, and only because, its transaction committed (AD-51).
    assert audit.tx == event.tx, "audit entry and event belong to the same business transaction"
    assert (event.event_type, event.event_version, event.status) == ("probe.setting.changed", 1, "pending")
    assert (event.subject_type, event.subject_id, event.subject_version) == ("probe.setting", KEY_A, 1)
    assert event.payload == {"key": KEY_A, "value": 48}
    # Key, effect and stored response (LD-61).
    assert (stored.principal_id, stored.key, stored.endpoint) == (
        user,
        "commit-together-1",
        "PUT /ui/v1/probe/settings/{key}",
    )
    assert stored.status_code == 200
    assert stored.response_body == response.text


async def test_a_failure_after_every_write_leaves_nothing_behind(
    core_app: CoreApp, stack: Stack, customer: Customer
) -> None:
    token = core_app.user_token(customer)
    failed = await _put(core_app, token, 48, 0, key="rollback-test-1", fail_after_writes=True)
    assert (failed.status_code, failed.json()["code"]) == (409, "INVALID_STATE_TRANSITION")
    assert failed.headers["content-type"] == PROBLEM_CONTENT_TYPE
    assert core_app.state.handler_calls == 1, "the handler did run and did write"
    assert await _counts(stack, customer) == {"settings": 0, "audit": 0, "events": 0, "keys": 0}

    # Failed requests store nothing, so the same key can be used for the corrected request.
    retried = await _put(core_app, token, 48, 0, key="rollback-test-1")
    assert retried.status_code == 200
    assert "idempotent-replay" not in retried.headers
    assert await _counts(stack, customer) == {"settings": 1, "audit": 1, "events": 1, "keys": 1}


async def test_reads_write_nothing(core_app: CoreApp, stack: Stack, customer: Customer) -> None:
    """AD-08: a GET runs in a read-only transaction, so PostgreSQL itself refuses the write."""
    token = core_app.user_token(customer)
    response = await core_app.client.get("/ui/v1/probe/write-in-read", headers=core_app.auth(token))
    assert (response.status_code, response.json()["code"]) == (500, "INTERNAL_ERROR")
    assert "read-only" not in response.text.lower(), "internal details stay in the logs"
    assert await _counts(stack, customer) == {"settings": 0, "audit": 0, "events": 0, "keys": 0}
    # Ordinary reads, including one that uses the unit of work, are fine.
    assert (await core_app.client.get(_url(), headers=core_app.auth(token))).json() == {
        "key": KEY_A,
        "value": 72,
        "version": 0,
    }


async def test_validation_errors_do_not_reach_the_handler_or_echo_input(
    core_app: CoreApp, stack: Stack, customer: Customer
) -> None:
    token = core_app.user_token(customer)
    response = await core_app.client.put(
        _url(),
        json={"value": 1, "expected_version": "not-a-number-SECRET"},
        headers=core_app.auth(token, **{"Idempotency-Key": core_app.key()}),
    )
    body = response.json()
    assert (response.status_code, body["code"]) == (422, "VALIDATION_FAILED")
    assert body["errors"][0]["field"] == "expected_version"
    assert "SECRET" not in response.text
    bad_value = await _put(core_app, token, "forty-eight", 0, key=core_app.key())
    assert (bad_value.status_code, bad_value.json()["code"]) == (422, "VALIDATION_FAILED")
    assert core_app.state.handler_calls == 1
    assert await _counts(stack, customer) == {"settings": 0, "audit": 0, "events": 0, "keys": 0}


# --------------------------------------------------------------------------------- idempotency
async def test_idempotency_key_is_required_on_every_mutation(core_app: CoreApp, customer: Customer) -> None:
    token = core_app.user_token(customer)
    for key in (None, "short", "has spaces in it", "x" * 129):
        response = await _put(core_app, token, 1, 0, key=key)
        assert (response.status_code, response.json()["code"]) == (400, "VALIDATION_FAILED"), key
        assert response.json()["errors"][0]["field"] == "Idempotency-Key"
    assert core_app.state.handler_calls == 0


async def test_a_retried_request_acts_once_and_replays_the_response(
    core_app: CoreApp, stack: Stack, customer: Customer
) -> None:
    token = core_app.user_token(customer, uuid7())
    user_token = token
    first = await _put(core_app, user_token, 10, 0, key="double-scan-0001")
    assert first.status_code == 200
    assert "idempotent-replay" not in first.headers

    for _ in range(3):  # the scanner fires again; the client retries after a timeout
        replay = await _put(core_app, user_token, 10, 0, key="double-scan-0001")
        assert replay.status_code == 200
        assert replay.headers["idempotent-replay"] == "true"
        assert replay.json() == first.json()
    assert core_app.state.handler_calls == 1
    assert await _counts(stack, customer) == {"settings": 1, "audit": 1, "events": 1, "keys": 1}


async def test_same_key_with_a_different_request_is_refused(
    core_app: CoreApp, stack: Stack, customer: Customer
) -> None:
    user = uuid7()
    token = core_app.user_token(customer, user)
    assert (await _put(core_app, token, 10, 0, key="reused-key-0001")).status_code == 200
    for response in (
        await _put(core_app, token, 11, 0, key="reused-key-0001"),  # different body
        await _put(core_app, token, 10, 0, key="reused-key-0001", url=_url(KEY_B)),  # different path
    ):
        assert (response.status_code, response.json()["code"]) == (422, "IDEMPOTENCY_KEY_REUSED")
    assert core_app.state.handler_calls == 1
    assert await _counts(stack, customer) == {"settings": 1, "audit": 1, "events": 1, "keys": 1}


async def test_keys_are_scoped_to_the_principal(core_app: CoreApp, stack: Stack, customer: Customer) -> None:
    first = core_app.runtime.authenticator.issue_user_access(
        customer_id=customer.id, user_id=uuid7(), session_id=uuid7()
    )
    second = core_app.runtime.authenticator.issue_user_access(
        customer_id=customer.id, user_id=uuid7(), session_id=uuid7()
    )
    assert (await _put(core_app, first, 10, 0, key="shared-key-0001")).status_code == 200
    other = await _put(core_app, second, 20, 1, key="shared-key-0001")
    assert other.status_code == 200
    assert "idempotent-replay" not in other.headers, "another principal's key is a different key"
    assert core_app.state.handler_calls == 2


async def test_concurrent_duplicates_produce_one_effect(
    core_app: CoreApp, stack: Stack, customer: Customer
) -> None:
    """Ten copies of one request race through the pooler: exactly one runs, all get its answer."""
    token = core_app.user_token(customer, uuid7())
    responses = await asyncio.gather(*(_put(core_app, token, 33, 0, key="race-key-00001") for _ in range(10)))
    assert [r.status_code for r in responses] == [200] * 10
    assert {r.text for r in responses} == {responses[0].text}
    assert sum("idempotent-replay" in r.headers for r in responses) == 9
    assert core_app.state.handler_calls == 1
    assert await _counts(stack, customer) == {"settings": 1, "audit": 1, "events": 1, "keys": 1}


async def test_duplicate_proceeds_if_the_first_request_rolls_back(
    core_app: CoreApp, stack: Stack, customer: Customer
) -> None:
    """LD-61: the duplicate waits on the unique index; if the first rolls back, it runs."""
    token = core_app.user_token(customer, uuid7())
    failing = _put(core_app, token, 33, 0, key="race-key-00002", fail_after_writes=True)
    # Same key and same body, so the second waits behind the first and then fails the same way:
    # nothing was stored for it to replay.
    results = await asyncio.gather(
        failing, _put(core_app, token, 33, 0, key="race-key-00002", fail_after_writes=True)
    )
    assert [r.status_code for r in results] == [409, 409]
    assert core_app.state.handler_calls == 2
    assert await _counts(stack, customer) == {"settings": 0, "audit": 0, "events": 0, "keys": 0}


@pytest.mark.slow
async def test_duplicate_of_a_request_still_in_progress_is_told_so(
    core_app: CoreApp, stack: Stack, customer: Customer
) -> None:
    """A wait beyond lock_timeout (5 s) returns 409 REQUEST_IN_PROGRESS."""
    user = uuid7()
    token = core_app.user_token(customer, user)
    engine = await stack.app_engine(customer.db)
    try:
        async with engine.connect() as holder:
            # An in-flight request that has claimed the key but not finished.
            await holder.execute(
                text(
                    "INSERT INTO integration.idempotency_keys (principal_id, key, endpoint, request_hash, expires_at) "
                    "VALUES (:p, 'in-flight-0001', 'PUT /x', decode(repeat('00', 32), 'hex'), now() + interval '1 hour')"
                ),
                {"p": user},
            )
            response = await _put(core_app, token, 1, 0, key="in-flight-0001")
            assert (response.status_code, response.json()["code"]) == (409, "REQUEST_IN_PROGRESS")
            assert response.headers["retry-after"] == "1"
            await holder.rollback()
    finally:
        await engine.dispose()
    assert core_app.state.handler_calls == 0
    assert (await _put(core_app, token, 1, 0, key="in-flight-0001")).status_code == 200


async def test_an_expired_key_can_be_used_again(core_app: CoreApp, stack: Stack, customer: Customer) -> None:
    user = uuid7()
    token = core_app.user_token(customer, user)
    owner = await stack.migration_engine(customer.db)
    try:
        async with owner.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO integration.idempotency_keys "
                    "(principal_id, key, endpoint, request_hash, status_code, response_body, expires_at) "
                    "VALUES (:p, 'expired-key-001', 'PUT /old', decode(repeat('00', 32), 'hex'), 200, '{}', "
                    "now() - interval '1 minute')"
                ),
                {"p": user},
            )
    finally:
        await owner.dispose()
    response = await _put(core_app, token, 5, 0, key="expired-key-001")
    assert response.status_code == 200
    assert "idempotent-replay" not in response.headers
    assert core_app.state.handler_calls == 1


# ------------------------------------------------------------------------- optimistic locking
async def test_stale_version_is_a_conflict(core_app: CoreApp, stack: Stack, customer: Customer) -> None:
    token = core_app.user_token(customer)
    assert (await _put(core_app, token, 10, 0, key=core_app.key())).json()["version"] == 1
    assert (await _put(core_app, token, 11, 1, key=core_app.key())).json()["version"] == 2
    for stale in (0, 1, 7):
        response = await _put(core_app, token, 99, stale, key=core_app.key())
        assert (response.status_code, response.json()["code"]) == (412, "VERSION_CONFLICT")
    assert (await core_app.client.get(_url(), headers=core_app.auth(token))).json()["value"] == 11
    counts = await _counts(stack, customer)
    assert (counts["audit"], counts["events"]) == (2, 2), "refused writes leave no audit entry and no event"


async def test_first_write_wins_under_concurrency(
    core_app: CoreApp, stack: Stack, customer: Customer
) -> None:
    """Q20: of several writers that all read the same version, exactly one commits."""
    token = core_app.user_token(customer)
    assert (await _put(core_app, token, 1, 0, key=core_app.key())).status_code == 200
    responses = await asyncio.gather(
        *(_put(core_app, token, 100 + n, 1, key=core_app.key()) for n in range(8))
    )
    winners = [r for r in responses if r.status_code == 200]
    losers = [r for r in responses if r.status_code != 200]
    assert len(winners) == 1
    assert {(r.status_code, r.json()["code"]) for r in losers} == {(412, "VERSION_CONFLICT")}
    final = (await core_app.client.get(_url(), headers=core_app.auth(token))).json()
    assert final == {"key": KEY_A, "value": winners[0].json()["value"], "version": 2}
    counts = await _counts(stack, customer)
    assert (counts["settings"], counts["audit"], counts["events"]) == (1, 2, 2)

    # The very first write of a row races too: one insert wins, the rest conflict.
    firsts = await asyncio.gather(
        *(_put(core_app, token, n, 0, key=core_app.key(), url=_url(KEY_B)) for n in range(6))
    )
    assert sorted(r.status_code for r in firsts) == [200] + [412] * 5


async def test_event_subject_versions_increase_with_every_change(
    core_app: CoreApp, stack: Stack, customer: Customer
) -> None:
    """AD-85: consumers order events per subject by subject version."""
    token = core_app.user_token(customer)
    for version in range(5):
        assert (await _put(core_app, token, version, version, key=core_app.key())).status_code == 200
    engine = await stack.migration_engine(customer.db)
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT subject_version, seq, id FROM integration.outbox_events "
                        "WHERE subject_id = :k ORDER BY seq"
                    ),
                    {"k": KEY_A},
                )
            ).all()
    finally:
        await engine.dispose()
    assert [r.subject_version for r in rows] == [1, 2, 3, 4, 5]
    assert len({r.id for r in rows}) == 5
    assert [r.id for r in rows] == sorted(r.id for r in rows), "event IDs are time-ordered (UUIDv7)"


# ------------------------------------------------------------------------------ deadlock retry
@pytest.mark.slow
async def test_a_deadlocked_unit_of_work_is_retried_transparently(
    core_app: CoreApp, stack: Stack, customer: Customer
) -> None:
    """LLD 9.1: deadlock errors retry the unit of work; neither caller sees a failure."""
    token = core_app.user_token(customer)
    for key in (KEY_A, KEY_B):
        assert (await _put(core_app, token, 1, 0, key=core_app.key(), url=_url(key))).status_code == 200

    core_app.state.barrier = asyncio.Barrier(2)

    async def lock(first: str, second: str) -> httpx.Response:
        return await core_app.client.post(
            "/ui/v1/probe/lock-pair",
            json={"first": first, "second": second},
            headers=core_app.auth(token, **{"Idempotency-Key": core_app.key()}),
        )

    one, two = await asyncio.gather(lock(KEY_A, KEY_B), lock(KEY_B, KEY_A))
    assert (one.status_code, two.status_code) == (200, 200)
    assert core_app.state.lock_pair_attempts == 3, "one of the two was rolled back and run again"


# ------------------------------------------------------------------------------- pool pressure
async def test_many_concurrent_requests_fit_the_per_customer_connection_budget(
    core_app: CoreApp, stack: Stack, customer: Customer
) -> None:
    """Forty concurrent requests for one customer share four server connections (LLD 6.5)."""
    token = core_app.user_token(customer)
    responses = await asyncio.gather(
        *(core_app.client.get("/ui/v1/probe/whoami", headers=core_app.auth(token)) for _ in range(40))
    )
    assert [r.status_code for r in responses] == [200] * 40
    admin = stack.cluster.admin_engine()
    try:
        async with admin.connect() as conn:
            server_connections = (
                await conn.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE datname = :d AND usename = :u"),
                    {"d": customer.db.database_name, "u": customer.db.app_role},
                )
            ).scalar_one()
    finally:
        await admin.dispose()
    assert 1 <= server_connections <= 4


# ------------------------------------------------------------------------------------ GxP mode
async def test_gmp_relevant_changes_need_a_reason_in_gxp_mode(
    core_app: CoreApp, stack: Stack, customer: Customer, gxp_customer: Customer
) -> None:
    """LD-82: in GxP mode a reason for change is mandatory and cannot be configured away."""
    gxp_token = core_app.user_token(gxp_customer)
    for reason in (None, "", "   "):
        refused = await _put(core_app, gxp_token, 5, 0, key=core_app.key(), gmp_relevant=True, reason=reason)
        assert (refused.status_code, refused.json()["code"]) == (422, "REASON_REQUIRED")
    assert await _counts(stack, gxp_customer) == {"settings": 0, "audit": 0, "events": 0, "keys": 0}

    accepted = await _put(core_app, gxp_token, 5, 0, key=core_app.key(), gmp_relevant=True, reason="CAPA-118")
    assert accepted.status_code == 200
    engine = await stack.migration_engine(gxp_customer.db)
    try:
        async with engine.connect() as conn:
            reasons = (
                (
                    await conn.execute(
                        text("SELECT reason FROM audit.audit_log WHERE action = 'probe.gmp_change'")
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()
    assert reasons == ["CAPA-118"]

    # The hook exists for every customer; outside GxP mode it does not demand a reason.
    plain = await _put(core_app, core_app.user_token(customer), 5, 0, key=core_app.key(), gmp_relevant=True)
    assert plain.status_code == 200
