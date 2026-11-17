"""Control-Plane database and Licence Registry (LLD section 4, 6.8; AD-12, AD-13, AD-78)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ims_common.clock import ManualClock
from ims_common.ids import uuid7
from ims_common.objectstore import ObjectNotFoundError
from ims_common.pg import SQLSTATE_INSUFFICIENT_PRIVILEGE, sqlstate_of
from ims_common.problem import DomainError
from ims_common.secrets import SecretAccessDeniedError
from ims_common.service_auth import ServiceTokenIssuer
from ims_common.snapshot_bundle import BUNDLE_OBJECT_KEY, unseal
from ims_common.tokens import KeySet
from ims_contracts.enums import ChangeType, CustomerStatus, DatabaseStatus, Placement
from ims_contracts.errors import PROBLEM_CONTENT_TYPE, ErrorCode
from ims_contracts.licence import LicenceSnapshot, LicenceState, derive_state
from ims_core.kernel.licence import BundleSource
from ims_platform.registry import Actor, RegistryService
from ims_platform.runtime import PlatformRuntime
from tests.support.stack import ALL_MODULES, SETUP_ACTOR, Customer, Stack, onboard_customer

pytestmark = pytest.mark.db

OPERATOR = Actor("platform_user:test-operator", request_id="req-test-1")


async def _refused(awaitable) -> DomainError:
    with pytest.raises(DomainError) as excinfo:
        await awaitable
    return excinfo.value


# ------------------------------------------------------------------------------- lifecycle
async def test_a_customer_is_invisible_until_fully_provisioned(
    stack: Stack, session_registry: RegistryService, fresh_code: str
) -> None:
    registry = session_registry
    customer_id = await registry.register_customer(code=fresh_code, legal_name="Acme Ltd", actor=OPERATOR)
    assert await registry.get_snapshot(customer_id) is None, "never-licensed customers have no snapshot"

    # Activation needs an active licence and a migrated, ready database.
    error = await _refused(registry.activate_customer(customer_id, actor=OPERATOR))
    assert error.code is ErrorCode.INVALID_STATE_TRANSITION

    now = datetime.now(UTC)
    licence_id = await registry.create_licence(
        customer_id=customer_id,
        licence_no=f"LIC-{fresh_code}",
        valid_from=now,
        valid_until=now + timedelta(days=365),
        max_sites=3,
        max_users=50,
        modules=frozenset({"ims.core", "ims.integration"}),
        actor=OPERATOR,
    )
    await registry.activate_licence(licence_id, actor=OPERATOR)
    error = await _refused(registry.activate_customer(customer_id, actor=OPERATOR))
    assert "database" in (error.detail or "")

    await registry.register_database(
        customer_id=customer_id,
        cluster_ref=stack.cluster.cluster_ref,
        pooler_endpoint=stack.cluster.pooler_endpoint,
        database_name=f"ims_c_{fresh_code}",
        app_role=f"ims_app_{fresh_code}",
        secret_ref=f"customers/{fresh_code}/db-app",
        actor=OPERATOR,
    )
    error = await _refused(registry.activate_customer(customer_id, actor=OPERATOR))
    assert "database" in (error.detail or ""), "a database that is still 'creating' is not ready"
    await registry.record_database_state(
        customer_id, actor=OPERATOR, status=DatabaseStatus.READY, schema_version="0001"
    )
    assert await registry.get_snapshot(customer_id) is None, "still provisioning"
    await registry.activate_customer(customer_id, actor=OPERATOR)

    snapshot = await registry.get_snapshot(customer_id)
    assert snapshot is not None
    assert snapshot.customer_code == fresh_code
    assert snapshot.customer_status is CustomerStatus.ACTIVE
    assert snapshot.modules == {"ims.core", "ims.integration"}
    assert (snapshot.max_sites, snapshot.max_users, snapshot.grace_days) == (3, 50, 14)
    assert snapshot.db.database_name == f"ims_c_{fresh_code}"
    assert snapshot.db.secret_ref == f"customers/{fresh_code}/db-app"
    assert snapshot.db.schema_version == "0001"
    assert snapshot.placement is Placement.SHARED
    assert derive_state(snapshot, now) is LicenceState.ACTIVE


async def test_registry_stores_a_secret_reference_never_a_password(
    stack: Stack, session_registry: RegistryService, customer_a: Customer
) -> None:
    credential = await stack.pipeline_secrets.get(customer_a.db.app_secret_ref)
    engine = stack.cluster.admin_engine("ims_control_plane")
    try:
        async with engine.connect() as conn:
            dump = (
                await conn.execute(text("SELECT row_to_json(d)::text FROM platform.customer_databases d"))
            ).scalars()
            audit = (
                await conn.execute(text("SELECT row_to_json(a)::text FROM platform.platform_audit a"))
            ).scalars()
            everything = "\n".join([*dump, *audit])
    finally:
        await engine.dispose()
    assert customer_a.db.app_secret_ref in everything
    assert credential["password"] not in everything


async def test_customer_status_state_machine(
    session_registry: RegistryService, stack: Stack, fresh_code: str
) -> None:
    registry = session_registry
    customer = await onboard_customer(stack, registry, fresh_code, now=datetime.now(UTC))
    now = datetime.now(UTC)

    async def state() -> LicenceState:
        snapshot = await registry.get_snapshot(customer.id)
        assert snapshot is not None
        return derive_state(snapshot, now)

    assert await state() is LicenceState.ACTIVE
    assert (await _refused(registry.activate_customer(customer.id, actor=OPERATOR))).status == 409
    assert (
        await _refused(registry.reinstate_customer(customer.id, actor=OPERATOR, reason="x"))
    ).status == 409
    # A reason is mandatory for suspension and termination.
    assert (await _refused(registry.suspend_customer(customer.id, actor=OPERATOR, reason="  "))).status == 422

    await registry.suspend_customer(customer.id, actor=OPERATOR, reason="invoice overdue")
    assert await state() is LicenceState.SUSPENDED
    assert (
        await _refused(registry.suspend_customer(customer.id, actor=OPERATOR, reason="again"))
    ).status == 409
    await registry.reinstate_customer(customer.id, actor=OPERATOR, reason="paid")
    assert await state() is LicenceState.ACTIVE
    await registry.terminate_customer(customer.id, actor=OPERATOR, reason="contract ended")
    assert await state() is LicenceState.TERMINATED
    # Terminated is final.
    for attempt in (
        registry.reinstate_customer(customer.id, actor=OPERATOR, reason="x"),
        registry.suspend_customer(customer.id, actor=OPERATOR, reason="x"),
        registry.terminate_customer(customer.id, actor=OPERATOR, reason="x"),
    ):
        assert (await _refused(attempt)).code is ErrorCode.INVALID_STATE_TRANSITION


async def test_database_itself_refuses_illegal_registry_changes(
    stack: Stack, session_registry: RegistryService, customer_a: Customer, customer_gxp: Customer
) -> None:
    """The guards hold even for code that bypasses RegistryService (as platform_app)."""
    credential = await stack.platform_secrets.get("platform/db-app")
    engine = stack.pooled_engine("ims_control_plane", "platform_app", credential["password"])
    await session_registry.mark_gxp_locked(customer_gxp.id, actor=SETUP_ACTOR)

    async def rejected(sql: str, **params: object) -> str | None:
        with pytest.raises(DBAPIError) as excinfo:
            async with engine.begin() as conn:
                await conn.execute(text(sql), params)
        return sqlstate_of(excinfo.value)

    try:
        a, g = customer_a.id, customer_gxp.id
        # Status transitions outside the state machine.
        assert await rejected("UPDATE platform.customers SET status = 'provisioning' WHERE id = :i", i=a)
        assert await rejected("UPDATE platform.customers SET status = 'bogus' WHERE id = :i", i=a)
        assert await rejected("UPDATE platform.customers SET code = 'renamed' WHERE id = :i", i=a)
        # GxP: the lock is permanent, and with it GxP mode and the dedicated placement.
        assert await rejected("UPDATE platform.customers SET gxp_locked = false WHERE id = :i", i=g)
        assert await rejected("UPDATE platform.customers SET gxp_mode = false WHERE id = :i", i=g)
        assert await rejected("UPDATE platform.customers SET placement = 'shared' WHERE id = :i", i=g)
        assert await rejected("UPDATE platform.customers SET gxp_mode = true WHERE id = :i", i=a), (
            "GxP needs a dedicated instance"
        )
        # An activated licence's terms and modules are immutable; a renewal is a new record.
        lic = customer_a.licence_id
        assert await rejected(
            "UPDATE platform.licences SET valid_until = valid_until + interval '10 years' WHERE id = :i",
            i=lic,
        )
        assert await rejected("UPDATE platform.licences SET max_users = 100000 WHERE id = :i", i=lic)
        assert await rejected("UPDATE platform.licences SET record_status = 'draft' WHERE id = :i", i=lic)
        assert await rejected(
            "INSERT INTO platform.licence_modules (licence_id, module_code) VALUES (:i, 'ims.core') "
            "ON CONFLICT DO NOTHING",
            i=lic,
        )
        assert await rejected("DELETE FROM platform.licence_modules WHERE licence_id = :i", i=lic)
        # No hard deletes, and history is append-only.
        for sql in (
            "DELETE FROM platform.customers WHERE id = :i",
            "DELETE FROM platform.licences WHERE customer_id = :i",
            "DELETE FROM platform.customer_databases WHERE customer_id = :i",
            "DELETE FROM platform.platform_audit WHERE customer_id = :i",
            "UPDATE platform.platform_audit SET actor = 'nobody' WHERE customer_id = :i",
            "DELETE FROM platform.change_feed WHERE customer_id = :i",
            "UPDATE platform.change_feed SET change_type = 'status' WHERE customer_id = :i",
        ):
            assert await rejected(sql, i=a) == SQLSTATE_INSUFFICIENT_PRIVILEGE, sql
        assert await rejected("TRUNCATE platform.platform_audit") == SQLSTATE_INSUFFICIENT_PRIVILEGE
        assert await rejected("CREATE TABLE platform.sneaky (id int)") == SQLSTATE_INSUFFICIENT_PRIVILEGE
        assert await rejected("ALTER TABLE platform.customers DISABLE TRIGGER customers_guard")
    finally:
        await engine.dispose()


async def test_gxp_rules(
    session_registry: RegistryService, customer_a: Customer, customer_gxp: Customer
) -> None:
    registry = session_registry
    error = await _refused(
        registry.register_customer(code="gxp_shared", legal_name="X", actor=OPERATOR, gxp_mode=True)
    )
    assert error.code is ErrorCode.VALIDATION_FAILED
    assert error.errors[0].field == "placement"

    snapshot = await registry.get_snapshot(customer_gxp.id)
    assert snapshot is not None
    assert snapshot.gxp_mode
    assert snapshot.placement is Placement.DEDICATED
    await registry.mark_gxp_locked(customer_gxp.id, actor=OPERATOR)
    assert await registry.mark_gxp_locked(customer_gxp.id, actor=OPERATOR) is False, "idempotent"
    locked = await registry.get_snapshot(customer_gxp.id)
    assert locked is not None
    assert locked.gxp_locked
    # Only GxP customers can hold GxP data.
    assert (await _refused(registry.mark_gxp_locked(customer_a.id, actor=OPERATOR))).status == 409


async def test_renewal_supersedes_the_previous_licence(
    session_registry: RegistryService, stack: Stack, fresh_code: str
) -> None:
    registry = session_registry
    start = datetime.now(UTC)
    customer = await onboard_customer(
        stack, registry, fresh_code, now=start, valid_for_days=10, grace_days=14
    )
    long_after = start + timedelta(days=40)
    expired = await registry.get_snapshot(customer.id)
    assert expired is not None
    assert derive_state(expired, long_after) is LicenceState.READ_ONLY

    renewal = await registry.create_licence(
        customer_id=customer.id,
        licence_no=f"LIC-{fresh_code}-2",
        valid_from=start,
        valid_until=start + timedelta(days=400),
        max_sites=9,
        max_users=500,
        modules=frozenset({"ims.core"}),
        grace_days=30,
        actor=OPERATOR,
    )
    draft_view = await registry.get_snapshot(customer.id)
    assert draft_view is not None
    assert draft_view.max_users == 200, "a draft licence has no effect"
    await registry.activate_licence(renewal, actor=OPERATOR)

    renewed = await registry.get_snapshot(customer.id)
    assert renewed is not None
    assert derive_state(renewed, long_after) is LicenceState.ACTIVE, "renewal returns read-only to active"
    assert (renewed.max_sites, renewed.max_users, renewed.grace_days) == (9, 500, 30)
    assert renewed.modules == {"ims.core"}
    assert (await _refused(registry.activate_licence(renewal, actor=OPERATOR))).status == 409
    assert (await _refused(registry.activate_licence(customer.licence_id, actor=OPERATOR))).status == 409

    engine = stack.cluster.admin_engine("ims_control_plane")
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT record_status, count(*) FROM platform.licences WHERE customer_id = :c GROUP BY 1"
                    ),
                    {"c": customer.id},
                )
            ).all()
    finally:
        await engine.dispose()
    assert dict(rows) == {"active": 1, "superseded": 1}


async def test_licence_validation(session_registry: RegistryService, customer_a: Customer) -> None:
    registry = session_registry
    now = datetime.now(UTC)
    base = {
        "customer_id": customer_a.id,
        "valid_from": now,
        "valid_until": now + timedelta(days=30),
        "max_sites": 1,
        "max_users": 1,
        "modules": ALL_MODULES,
        "actor": OPERATOR,
    }
    cases = [
        ({"licence_no": "V-1", "valid_until": now - timedelta(days=1)}, "valid_until"),
        ({"licence_no": "V-2", "modules": frozenset()}, "modules"),
        ({"licence_no": "V-3", "modules": frozenset({"ims.core", "ims.nope"})}, "modules"),
        ({"licence_no": "V-4", "valid_from": datetime(2026, 1, 1)}, "valid_until"),  # noqa: DTZ001 - naive on purpose
        ({"licence_no": "LIC-alpha-1"}, "licence_no"),  # duplicate number
        ({"licence_no": "V-6", "max_users": 0}, "licence"),
    ]
    for overrides, field in cases:
        error = await _refused(registry.create_licence(**{**base, **overrides}))
        assert (error.status, error.errors[0].field) == (422, field), overrides
    assert (
        await _refused(registry.create_licence(**{**base, "customer_id": uuid7(), "licence_no": "V-7"}))
    ).status == 404


@pytest.mark.parametrize("code", ["A", "1abc", "has-dash", "UPPER", "a", "x" * 31, "semi;colon", ""])
async def test_customer_code_must_be_safe_for_database_and_role_names(
    session_registry: RegistryService, code: str
) -> None:
    error = await _refused(session_registry.register_customer(code=code, legal_name="X", actor=OPERATOR))
    assert error.code is ErrorCode.VALIDATION_FAILED


async def test_customer_code_is_unique(session_registry: RegistryService, customer_a: Customer) -> None:
    error = await _refused(
        session_registry.register_customer(code=customer_a.code, legal_name="X", actor=OPERATOR)
    )
    assert error.errors[0].message == "customer code is already in use"


# ---------------------------------------------------------------- change feed and audit
async def test_every_command_is_audited_and_announced_in_one_transaction(
    stack: Stack, session_registry: RegistryService, fresh_code: str
) -> None:
    registry = session_registry
    before = (await registry.changes(None)).head_seq
    customer = await onboard_customer(stack, registry, fresh_code, now=datetime.now(UTC))
    await registry.suspend_customer(customer.id, actor=OPERATOR, reason="audit test")

    page = await registry.changes(before)
    mine = [e for e in page.entries if e.customer_id == customer.id]
    assert [e.change_type for e in mine] == [
        ChangeType.DATABASE,  # ready + schema version
        ChangeType.LICENCE,
        ChangeType.STATUS,  # activated
        ChangeType.STATUS,  # suspended
    ]
    assert [e.seq for e in page.entries] == sorted(e.seq for e in page.entries)
    assert page.head_seq == page.entries[-1].seq
    assert (await registry.changes(page.head_seq)).entries == []
    assert len((await registry.changes(before, limit=2)).entries) == 2

    engine = stack.cluster.admin_engine("ims_control_plane")
    try:
        async with engine.connect() as conn:
            audit = (
                await conn.execute(
                    text(
                        "SELECT action, actor, reason, request_id, before, after FROM platform.platform_audit "
                        "WHERE customer_id = :c ORDER BY seq"
                    ),
                    {"c": customer.id},
                )
            ).all()
    finally:
        await engine.dispose()
    assert [row.action for row in audit] == [
        "customer.registered",
        "database.registered",
        "database.state_recorded",
        "licence.created",
        "licence.activated",
        "customer.activated",
        "customer.suspended",
    ]
    suspended = audit[-1]
    assert (suspended.actor, suspended.reason, suspended.request_id) == (
        OPERATOR.ref,
        "audit test",
        "req-test-1",
    )
    assert (suspended.before, suspended.after) == ({"status": "active"}, {"status": "suspended"})


async def test_change_feed_order_is_commit_order(
    stack: Stack, customer_a: Customer, customer_b: Customer
) -> None:
    """A poller reading "seq > N" must never be able to skip a change that commits late.

    Two writers: the first takes its sequence number and stays open. The second cannot take a
    number until the first finishes, so no higher number is ever visible before a lower one.
    """
    credential = await stack.platform_secrets.get("platform/db-app")
    engine = stack.pooled_engine("ims_control_plane", "platform_app", credential["password"], pool_size=3)
    insert = text(
        "INSERT INTO platform.change_feed (customer_id, change_type) VALUES (:c, 'licence') RETURNING seq"
    )
    head = text("SELECT COALESCE(max(seq), 0) FROM platform.change_feed")
    try:
        async with engine.connect() as first, engine.connect() as second, engine.connect() as reader:
            start = (await reader.execute(head)).scalar_one()
            await reader.commit()

            await first.begin()
            seq_first = (await first.execute(insert, {"c": customer_a.id})).scalar_one()

            await second.begin()
            pending = asyncio.create_task(second.execute(insert, {"c": customer_b.id}))
            done, _ = await asyncio.wait({pending}, timeout=0.7)
            assert not done, "the second writer must wait for the first to commit"
            assert (await reader.execute(head)).scalar_one() == start, "nothing visible yet"
            await reader.commit()

            await first.commit()
            seq_second = (await pending).scalar_one()
            await second.commit()
            assert seq_second > seq_first > start
            visible = (
                (
                    await reader.execute(
                        text("SELECT seq FROM platform.change_feed WHERE seq > :s ORDER BY seq"), {"s": start}
                    )
                )
                .scalars()
                .all()
            )
            assert visible == [seq_first, seq_second]
    finally:
        await engine.dispose()


async def test_a_rolled_back_command_leaves_no_notice(
    session_registry: RegistryService, customer_a: Customer
) -> None:
    registry = session_registry
    before = (await registry.changes(None)).head_seq
    await _refused(registry.activate_customer(customer_a.id, actor=OPERATOR))  # already active
    assert (await registry.changes(before)).entries == []


# ------------------------------------------------------------------------ internal interface
@pytest.fixture
def platform_client(platform_app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=platform_app), base_url="http://platform")


def _bearer(
    stack: Stack, service: str, clock: ManualClock, audience: str = "platform-internal"
) -> dict[str, str]:
    token = ServiceTokenIssuer(service, stack.service_keys[service], clock).token_for(audience)
    return {"Authorization": f"Bearer {token}"}


async def test_internal_interface_requires_a_trusted_service_token(
    stack: Stack, platform_client: httpx.AsyncClient, clock: ManualClock, customer_a: Customer
) -> None:
    url = f"/internal/v1/customers/{customer_a.id}/snapshot"
    async with platform_client as client:
        ok = await client.get(url, headers=_bearer(stack, "ims-core", clock))
        assert ok.status_code == 200
        assert LicenceSnapshot.model_validate(ok.json()).customer_code == customer_a.code
        assert (await client.get(url, headers=_bearer(stack, "ims-worker", clock))).status_code == 200

        stranger = ServiceTokenIssuer("ims-core", KeySet.generate("x"), clock).token_for("platform-internal")
        refusals = [
            {},  # no token
            {"Authorization": "Bearer not-a-token"},
            _bearer(stack, "tenant-web-bff", clock),  # a real service, but not a trusted caller
            _bearer(stack, "ims-core", clock, audience="ims-core-internal"),  # wrong audience
            {"Authorization": f"Bearer {stranger}"},  # right name, wrong key
        ]
        for headers in refusals:
            for path in (url, "/internal/v1/changes"):
                response = await client.get(path, headers=headers)
                assert response.status_code == 401, headers
                assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
                assert response.json()["code"] == "AUTH_REQUIRED"

        expired = _bearer(stack, "ims-core", ManualClock(clock.now() - timedelta(minutes=10)))
        response = await client.get(url, headers=expired)
        assert (response.status_code, response.json()["code"]) == (401, "TOKEN_EXPIRED")


async def test_snapshot_endpoint_refuses_unknown_and_unlicensed_customers(
    stack: Stack,
    platform_client: httpx.AsyncClient,
    clock: ManualClock,
    session_registry: RegistryService,
    fresh_code: str,
) -> None:
    provisioning = await session_registry.register_customer(
        code=fresh_code, legal_name="Pending", actor=OPERATOR
    )
    headers = _bearer(stack, "ims-core", clock)
    async with platform_client as client:
        for customer_id in (uuid7(), provisioning):
            response = await client.get(f"/internal/v1/customers/{customer_id}/snapshot", headers=headers)
            assert response.status_code == 404
            assert response.json()["code"] == "NOT_FOUND"
        assert (
            await client.get("/internal/v1/customers/not-a-uuid/snapshot", headers=headers)
        ).status_code == 422


async def test_changes_endpoint(
    stack: Stack,
    platform_client: httpx.AsyncClient,
    clock: ManualClock,
    session_registry: RegistryService,
    customer_gxp: Customer,
) -> None:
    headers = _bearer(stack, "ims-core", clock)
    async with platform_client as client:
        head = (await client.get("/internal/v1/changes", headers=headers)).json()
        assert head["entries"] == []
        after = head["head_seq"]
        await session_registry.record_database_state(
            customer_gxp.id, actor=OPERATOR, status=DatabaseStatus.MIGRATING
        )
        await session_registry.record_database_state(
            customer_gxp.id, actor=OPERATOR, status=DatabaseStatus.READY
        )
        page = (await client.get("/internal/v1/changes", params={"after_seq": after}, headers=headers)).json()
        assert [(e["customer_id"], e["change_type"]) for e in page["entries"]] == [
            (str(customer_gxp.id), "database")
        ] * 2
        assert page["head_seq"] == page["entries"][-1]["seq"] == after + 2
        assert (await client.get("/internal/v1/changes?after_seq=-1", headers=headers)).status_code == 422


# ---------------------------------------------------------------------------- snapshot bundle
async def test_bundle_is_published_signed_and_usable_by_core(
    stack: Stack,
    platform: PlatformRuntime,
    customer_a: Customer,
    customer_b: Customer,
    fresh_code: str,
    session_registry: RegistryService,
) -> None:
    provisioning = await session_registry.register_customer(
        code=fresh_code, legal_name="Pending", actor=OPERATOR
    )
    published = await platform.bundle_publisher.publish_once()
    raw = await stack.object_store.get(BUNDLE_OBJECT_KEY)

    verify_keys = KeySet.from_secret(await stack.core_secrets.get("platform/bundle-verify"))
    opened = unseal(raw, verify_keys)
    ids = {s.customer_id for s in opened.snapshots}
    assert {customer_a.id, customer_b.id} <= ids
    assert provisioning not in ids, "never-licensed customers are not in the bundle"
    assert opened.feed_seq == published.feed_seq > 0

    loaded = await BundleSource(stack.object_store, verify_keys).load()
    assert loaded is not None
    assert {s.customer_id for s in loaded.snapshots} == ids

    # Whoever can write to the bucket still cannot grant anything: a modified bundle is ignored.
    envelope = json.loads(raw)
    envelope["payload"] = envelope["payload"][:-8] + "AAAAAAA="
    await stack.object_store.put(
        BUNDLE_OBJECT_KEY, json.dumps(envelope).encode(), content_type="application/json"
    )
    assert await BundleSource(stack.object_store, verify_keys).load() is None
    await platform.bundle_publisher.publish_once()  # leave a valid bundle behind
    assert await BundleSource(stack.object_store, verify_keys).load() is not None


async def test_missing_bundle_is_not_an_error(tmp_path, stack: Stack) -> None:
    from ims_common.objectstore import FileObjectStore  # noqa: PLC0415

    empty = FileObjectStore(tmp_path)
    with pytest.raises(ObjectNotFoundError):
        await empty.get(BUNDLE_OBJECT_KEY)
    keys = KeySet.from_secret(await stack.core_secrets.get("platform/bundle-verify"))
    assert await BundleSource(empty, keys).load() is None


# ----------------------------------------------------------------------------- trust boundary
async def test_platform_identity_cannot_read_customer_data_credentials(
    stack: Stack, customer_a: Customer
) -> None:
    """AD-13: no credential on the platform tier reads business data or runs DDL."""
    for ref in (
        customer_a.db.app_secret_ref,
        customer_a.db.migration_secret_ref,
        "clusters/test-shared-1/admin",
    ):
        with pytest.raises(SecretAccessDeniedError):
            await stack.platform_secrets.get(ref)


async def test_platform_role_cannot_enter_a_customer_database(stack: Stack, customer_a: Customer) -> None:
    credential = await stack.platform_secrets.get("platform/db-app")
    for engine in (
        stack.pooled_engine(customer_a.db.database_name, "platform_app", credential["password"]),
        stack.cluster.engine_as(customer_a.db.database_name, "platform_app", credential["password"]),
    ):
        try:
            with pytest.raises(DBAPIError):
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()
