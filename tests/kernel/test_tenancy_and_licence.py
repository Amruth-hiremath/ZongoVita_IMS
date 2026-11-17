"""Tenant isolation and licence enforcement through the real request pipeline (LLD 6.1, 6.4).

Core talks to the real Platform Service (in-process, over its HTTP interface with service
tokens) and to real customer databases through the pooler.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import timedelta

import httpx
import pytest

from ims_common.clock import ManualClock
from ims_common.ids import uuid7
from ims_common.service_auth import ServiceTokenIssuer
from ims_common.tokens import KeySet, TokenCodec
from ims_contracts.enums import DatabaseStatus
from ims_contracts.errors import PROBLEM_CONTENT_TYPE
from ims_core.kernel.licence import ALARM_REGISTRY_UNREACHABLE
from ims_core.kernel.runtime import SERVICE_AUDIENCE_CORE_INTERNAL
from ims_platform.registry import Actor, RegistryService
from ims_platform.runtime import PlatformRuntime
from tests.conftest import CoreApp, SwitchableTransport, build_core_app, new_core_runtime
from tests.support.stack import Customer, Stack, onboard_customer

pytestmark = pytest.mark.db

OPERATOR = Actor("platform_user:test-operator")
WHOAMI = "/ui/v1/probe/whoami"
SETTING = "/ui/v1/probe/settings/probe.lock_timeout_hours"


def _problem(response: httpx.Response) -> tuple[int, str]:
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE, response.text
    body = response.json()
    assert body["request_id"] == response.headers["x-request-id"]
    assert body["type"].startswith("urn:zongovita:ims:problem:")
    return response.status_code, body["code"]


async def _put(
    app: CoreApp, token: str, value: int, expected_version: int, **extra: object
) -> httpx.Response:
    return await app.client.put(
        SETTING,
        json={"value": value, "expected_version": expected_version, **extra},
        headers=app.auth(token, **{"Idempotency-Key": app.key()}),
    )


# ---------------------------------------------------------------------------- tenant isolation
async def test_the_token_alone_decides_which_database_is_reached(
    core_app: CoreApp, customer_a: Customer, customer_b: Customer
) -> None:
    for customer in (customer_a, customer_b):
        response = await core_app.client.get(WHOAMI, headers=core_app.auth(core_app.user_token(customer)))
        assert response.status_code == 200
        body = response.json()
        assert body["customer_id"] == str(customer.id)
        assert body["customer_code"] == customer.code
        assert body["database"] == customer.db.database_name
        assert body["db_user"] == customer.db.app_role
        assert body["licence_state"] == "active"


async def test_no_request_input_can_select_another_customer(
    core_app: CoreApp, customer_a: Customer, customer_b: Customer
) -> None:
    """AD-21: no endpoint accepts a customer or database identifier."""
    token = core_app.user_token(customer_a)
    other = str(customer_b.id)
    response = await core_app.client.get(
        WHOAMI,
        params={
            "customer_id": other,
            "cid": other,
            "customer": customer_b.code,
            "database": customer_b.db.database_name,
        },
        headers=core_app.auth(
            token,
            **{
                "X-Customer-Id": other,
                "X-Tenant": customer_b.code,
                "X-Forwarded-Host": f"{customer_b.code}.ims.example",
                "Host": f"{customer_b.code}.ims.example",
            },
        ),
    )
    assert response.status_code == 200
    assert response.json()["database"] == customer_a.db.database_name


async def test_data_written_for_one_customer_does_not_exist_for_another(
    core_app: CoreApp, customer_a: Customer, customer_b: Customer
) -> None:
    token_a, token_b = core_app.user_token(customer_a), core_app.user_token(customer_b)
    current = (await core_app.client.get(SETTING, headers=core_app.auth(token_a))).json()
    written = await _put(core_app, token_a, 31, current["version"])
    assert written.status_code == 200
    assert (await core_app.client.get(SETTING, headers=core_app.auth(token_a))).json()["value"] == 31
    seen_by_b = (await core_app.client.get(SETTING, headers=core_app.auth(token_b))).json()
    assert seen_by_b["value"] != 31, "customer B still sees its own value"


def _swap_claim(token: str, **changes: str) -> str:
    header, payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims.update(changes)
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{forged}.{signature}"


async def test_tampered_or_foreign_tokens_are_rejected(
    core_app: CoreApp, clock: ManualClock, customer_a: Customer, customer_b: Customer
) -> None:
    token = core_app.user_token(customer_a)
    foreign_keys = KeySet.generate("core-2026-11")  # same key id as Core's, different key
    foreign = TokenCodec(foreign_keys, "ims-core", clock).encode(
        subject=str(uuid7()),
        audience="ims-ui",
        ttl=timedelta(minutes=15),
        claims={"ptype": "user", "cid": str(customer_b.id), "sid": str(uuid7())},
    )
    for bad in (_swap_claim(token, cid=str(customer_b.id)), foreign, token[:-4] + "AAAA", "garbage"):
        response = await core_app.client.get(WHOAMI, headers=core_app.auth(bad))
        assert _problem(response) == (401, "AUTH_REQUIRED")
        assert response.headers["www-authenticate"] == "Bearer"


async def test_authentication_failures(core_app: CoreApp, clock: ManualClock, customer_a: Customer) -> None:
    assert _problem(await core_app.client.get(WHOAMI)) == (401, "AUTH_REQUIRED")
    token = core_app.user_token(customer_a)
    api_token = core_app.api_token(customer_a)
    # Each API accepts only tokens issued for it.
    assert _problem(await core_app.client.get(WHOAMI, headers=core_app.auth(api_token))) == (
        401,
        "AUTH_REQUIRED",
    )
    assert _problem(await core_app.client.get("/api/v1/probe/whoami", headers=core_app.auth(token))) == (
        401,
        "AUTH_REQUIRED",
    )
    ok = await core_app.client.get("/api/v1/probe/whoami", headers=core_app.auth(api_token))
    assert ok.json() == {"customer_code": customer_a.code, "principal_type": "api_client"}

    clock.advance(seconds=15 * 60)  # access tokens live 15 minutes
    assert _problem(await core_app.client.get(WHOAMI, headers=core_app.auth(token))) == (401, "TOKEN_EXPIRED")


async def test_a_token_for_a_customer_that_was_never_licensed_is_refused(
    core_app: CoreApp, session_registry: RegistryService, fresh_code: str
) -> None:
    provisioning = await session_registry.register_customer(
        code=fresh_code, legal_name="Pending", actor=OPERATOR
    )
    for customer_id in (provisioning, uuid7()):
        response = await core_app.client.get(WHOAMI, headers=core_app.auth(core_app.user_token(customer_id)))
        assert _problem(response) == (401, "AUTH_REQUIRED")


async def test_stages_run_before_the_handler(core_app: CoreApp, customer_a: Customer) -> None:
    """Steps 6 and 8: an inactive principal or a missing permission stops the request, and
    nothing is written."""
    user = uuid7()
    token = core_app.user_token(customer_a, user)
    version = (await core_app.client.get(SETTING, headers=core_app.auth(token))).json()["version"]

    core_app.state.granted.clear()
    assert _problem(await _put(core_app, token, 5, version)) == (403, "PERMISSION_DENIED")
    core_app.state.granted.add("config.settings.manage")
    core_app.state.inactive_principals.add(user)
    assert _problem(await _put(core_app, token, 5, version)) == (401, "PRINCIPAL_INACTIVE")
    assert _problem(await core_app.client.get(WHOAMI, headers=core_app.auth(token))) == (
        401,
        "PRINCIPAL_INACTIVE",
    )

    assert core_app.state.handler_calls == 0
    other = core_app.user_token(customer_a)
    assert (await core_app.client.get(SETTING, headers=core_app.auth(other))).json()["version"] == version


async def test_credential_endpoints_get_no_tenant_context_from_the_pipeline(core_app: CoreApp) -> None:
    response = await core_app.client.post("/ui/v1/probe/credential")
    assert response.status_code == 200
    assert response.json() == {"has_uow": False}
    assert response.headers["x-request-id"]


# ---------------------------------------------------------------------------------- request ID
async def test_request_id_is_accepted_only_from_the_bff(
    core_app: CoreApp, stack: Stack, clock: ManualClock, customer_a: Customer
) -> None:
    token = core_app.user_token(customer_a)
    inbound = "bff-req-0001"

    plain = await core_app.client.get(WHOAMI, headers=core_app.auth(token, **{"X-Request-ID": inbound}))
    assert plain.headers["x-request-id"] != inbound, "an unauthenticated caller cannot choose the request ID"
    assert plain.json()["request_id"] == plain.headers["x-request-id"]

    def service_token(service: str, audience: str = SERVICE_AUDIENCE_CORE_INTERNAL) -> str:
        return ServiceTokenIssuer(service, stack.service_keys[service], clock).token_for(audience)

    trusted = await core_app.client.get(
        WHOAMI,
        headers=core_app.auth(
            token, **{"X-Request-ID": inbound, "X-IMS-Service-Token": service_token("tenant-web-bff")}
        ),
    )
    assert trusted.headers["x-request-id"] == inbound
    assert trusted.json()["request_id"] == inbound

    for headers in (
        {"X-Request-ID": inbound, "X-IMS-Service-Token": service_token("ims-worker")},  # not the BFF
        {
            "X-Request-ID": inbound,
            "X-IMS-Service-Token": service_token("tenant-web-bff", "platform-internal"),
        },
        {"X-Request-ID": "bad id with spaces", "X-IMS-Service-Token": service_token("tenant-web-bff")},
    ):
        response = await core_app.client.get(WHOAMI, headers=core_app.auth(token, **headers))
        assert response.headers["x-request-id"] not in (inbound, "bad id with spaces")


# -------------------------------------------------------------------------------- licence gate
async def test_licence_states_follow_the_clock_and_gate_every_request(
    core_app: CoreApp, clock: ManualClock, stack: Stack, session_registry: RegistryService, fresh_code: str
) -> None:
    customer = await onboard_customer(
        stack, session_registry, fresh_code, now=clock.now(), valid_for_days=10, grace_days=14
    )

    async def whoami() -> httpx.Response:
        return await core_app.client.get(WHOAMI, headers=core_app.auth(core_app.user_token(customer)))

    async def write(value: int) -> httpx.Response:
        token = core_app.user_token(customer)
        version = (await core_app.client.get(SETTING, headers=core_app.auth(token))).json()["version"]
        return await _put(core_app, token, value, version)

    assert (await whoami()).json()["licence_state"] == "active"
    assert (await write(1)).status_code == 200

    clock.set(customer.valid_until - timedelta(seconds=1))
    assert (await whoami()).json()["licence_state"] == "active"
    clock.set(customer.valid_until)  # the end date is reached: grace starts on time, full access
    assert (await whoami()).json()["licence_state"] == "grace"
    assert (await write(2)).status_code == 200

    clock.set(customer.valid_until + timedelta(days=14))  # grace over: read-only
    assert (await whoami()).json()["licence_state"] == "read_only"
    assert _problem(await write(3)) == (403, "LICENCE_READ_ONLY")
    token = core_app.user_token(customer)
    assert (await core_app.client.get(SETTING, headers=core_app.auth(token))).json()["value"] == 2
    # A route declared read_only_ok (emergency issue is the real one, LD-86) still works.
    emergency = await core_app.client.post(
        "/ui/v1/probe/emergency", headers=core_app.auth(token, **{"Idempotency-Key": core_app.key()})
    )
    assert emergency.status_code == 200

    # Renewal: a new licence is activated; the change notice brings the customer back to active.
    await core_app.runtime.snapshots.poll_changes_once()
    renewal = await session_registry.create_licence(
        customer_id=customer.id,
        licence_no=f"LIC-{fresh_code}-2",
        valid_from=clock.now(),
        valid_until=clock.now() + timedelta(days=365),
        max_sites=5,
        max_users=200,
        modules=frozenset({"ims.core"}),
        actor=OPERATOR,
    )
    await session_registry.activate_licence(renewal, actor=OPERATOR)
    assert _problem(await write(3)) == (403, "LICENCE_READ_ONLY"), "not yet notified, cache still fresh"
    assert await core_app.runtime.snapshots.poll_changes_once() >= 1
    assert (await whoami()).json()["licence_state"] == "active"
    assert (await write(3)).status_code == 200


async def test_unlicensed_module_is_refused_independently_of_permissions(
    core_app: CoreApp,
    clock: ManualClock,
    stack: Stack,
    session_registry: RegistryService,
    fresh_code: str,
    customer_a: Customer,
) -> None:
    core_only = await onboard_customer(
        stack, session_registry, fresh_code, now=clock.now(), modules=frozenset({"ims.core"})
    )
    path = "/ui/v1/probe/replenishment"

    def headers(customer: Customer) -> dict[str, str]:
        return core_app.auth(core_app.user_token(customer), **{"Idempotency-Key": core_app.key()})

    assert (await core_app.client.post(path, headers=headers(customer_a))).status_code == 200
    assert _problem(await core_app.client.post(path, headers=headers(core_only))) == (
        403,
        "MODULE_NOT_LICENSED",
    )
    assert (await core_app.client.get(WHOAMI, headers=headers(core_only))).status_code == 200
    # The public API belongs to the integration module, which this customer has not licensed.
    api = await core_app.client.get(
        "/api/v1/probe/whoami", headers=core_app.auth(core_app.api_token(core_only))
    )
    assert _problem(api) == (403, "MODULE_NOT_LICENSED")


async def test_suspension_and_termination_block_everything(
    core_app: CoreApp, clock: ManualClock, stack: Stack, session_registry: RegistryService, fresh_code: str
) -> None:
    customer = await onboard_customer(stack, session_registry, fresh_code, now=clock.now())
    snapshots = core_app.runtime.snapshots
    await snapshots.poll_changes_once()

    async def attempts() -> list[tuple[int, str]]:
        token = core_app.user_token(customer)
        return [
            _problem(await core_app.client.get(WHOAMI, headers=core_app.auth(token))),
            _problem(await _put(core_app, token, 9, 0)),
            _problem(
                await core_app.client.post(
                    "/ui/v1/probe/emergency",
                    headers=core_app.auth(token, **{"Idempotency-Key": core_app.key()}),
                )
            ),
        ]

    token = core_app.user_token(customer)
    assert (await core_app.client.get(WHOAMI, headers=core_app.auth(token))).status_code == 200

    await session_registry.suspend_customer(customer.id, actor=OPERATOR, reason="test")
    await snapshots.poll_changes_once()  # takes effect on the change notice, well inside the TTL
    assert await attempts() == [(403, "LICENCE_SUSPENDED")] * 3

    await session_registry.reinstate_customer(customer.id, actor=OPERATOR, reason="test")
    clock.advance(seconds=60)  # this time the notice is missed: the 60-second refresh covers it
    assert (
        await core_app.client.get(WHOAMI, headers=core_app.auth(core_app.user_token(customer)))
    ).status_code == 200

    await session_registry.terminate_customer(customer.id, actor=OPERATOR, reason="test")
    await snapshots.poll_changes_once()
    assert await attempts() == [(403, "LICENCE_TERMINATED")] * 3


# ----------------------------------------------------------------------------- Registry outage
async def test_registry_outage_never_blocks_a_known_customer(
    core_app: CoreApp,
    registry_link: SwitchableTransport,
    clock: ManualClock,
    customer_a: Customer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = core_app.user_token(customer_a)
    assert (await core_app.client.get(WHOAMI, headers=core_app.auth(token))).status_code == 200

    registry_link.down = True
    with caplog.at_level(logging.WARNING, logger="ims.licence"):
        for minutes in (2, 30, 600):  # far beyond the 60-second cache
            clock.advance(seconds=minutes * 60)
            token = core_app.user_token(customer_a)
            response = await core_app.client.get(WHOAMI, headers=core_app.auth(token))
            assert response.status_code == 200, "last known-good snapshot is honoured at any age"
            assert (
                await _put(
                    core_app,
                    token,
                    minutes,
                    (await core_app.client.get(SETTING, headers=core_app.auth(token))).json()["version"],
                )
            ).status_code == 200
    paged = [r for r in caplog.records if getattr(r, "alarm", None) == ALARM_REGISTRY_UNREACHABLE]
    assert [r.levelname for r in paged] == ["CRITICAL"], "on-call is paged once"
    assert core_app.app.state.runtime.snapshots.registry_reachable is False
    ready = (await core_app.client.get("/readyz")).json()
    assert ready == {"status": "ready", "registry_reachable": False}, "the instance stays in service"

    registry_link.down = False
    clock.advance(seconds=10)
    assert (
        await core_app.client.get(WHOAMI, headers=core_app.auth(core_app.user_token(customer_a)))
    ).status_code == 200
    assert core_app.app.state.runtime.snapshots.registry_reachable is True


async def test_a_process_started_during_an_outage_serves_from_the_signed_bundle(
    stack: Stack,
    platform: PlatformRuntime,
    registry_link: SwitchableTransport,
    clock: ManualClock,
    session_registry: RegistryService,
    customer_a: Customer,
    fresh_code: str,
) -> None:
    await platform.bundle_publisher.publish_once()
    # Licensed after the last bundle was written: unknown to a process that cannot ask.
    late = await onboard_customer(stack, session_registry, fresh_code, now=clock.now())

    registry_link.down = True
    runtime = await new_core_runtime(stack, clock, registry_link)  # a brand-new instance
    app, _ = build_core_app(runtime)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://core"
        ) as client:

            def bearer(customer: Customer) -> dict[str, str]:
                token = runtime.authenticator.issue_user_access(
                    customer_id=customer.id, user_id=uuid7(), session_id=uuid7()
                )
                return {"Authorization": f"Bearer {token}"}

            known = await client.get(WHOAMI, headers=bearer(customer_a))
            assert known.status_code == 200
            assert known.json()["database"] == customer_a.db.database_name

            unknown = await client.get(WHOAMI, headers=bearer(late))
            assert _problem(unknown) == (503, "LICENCE_UNVERIFIABLE")
            assert "retry-after" in unknown.headers

            registry_link.down = False
            clock.advance(seconds=10)
            assert (await client.get(WHOAMI, headers=bearer(late))).status_code == 200
    finally:
        await runtime.aclose()


# ---------------------------------------------------------------------------- database routing
async def test_schema_version_outside_the_supported_range_is_refused(
    core_app: CoreApp, clock: ManualClock, stack: Stack, session_registry: RegistryService, fresh_code: str
) -> None:
    customer = await onboard_customer(stack, session_registry, fresh_code, now=clock.now())
    headers = lambda: core_app.auth(core_app.user_token(customer))  # noqa: E731
    assert (await core_app.client.get(WHOAMI, headers=headers())).status_code == 200
    await core_app.runtime.snapshots.poll_changes_once()

    # A database being migrated keeps serving (online, expand-only migrations).
    await session_registry.record_database_state(customer.id, actor=OPERATOR, status=DatabaseStatus.MIGRATING)
    await core_app.runtime.snapshots.poll_changes_once()
    assert (await core_app.client.get(WHOAMI, headers=headers())).status_code == 200

    await session_registry.record_database_state(
        customer.id, actor=OPERATOR, status=DatabaseStatus.READY, schema_version="9999"
    )
    await core_app.runtime.snapshots.poll_changes_once()
    assert _problem(await core_app.client.get(WHOAMI, headers=headers())) == (
        503,
        "SCHEMA_VERSION_UNSUPPORTED",
    )

    await session_registry.record_database_state(
        customer.id, actor=OPERATOR, status=DatabaseStatus.FAILED, schema_version="0001"
    )
    await core_app.runtime.snapshots.poll_changes_once()
    busy = await core_app.client.get(WHOAMI, headers=headers())
    assert _problem(busy) == (503, "DB_BUSY")
    assert busy.headers["retry-after"] == "2"


async def test_rotated_database_credential_is_picked_up_without_a_restart(
    core_app: CoreApp,
    stack: Stack,
    clock: ManualClock,
    session_registry: RegistryService,
    fresh_code: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """LLD 6.5: credentials are re-fetched once on an authentication failure."""
    from sqlalchemy import text  # noqa: PLC0415

    customer = await onboard_customer(stack, session_registry, fresh_code, now=clock.now())
    headers = lambda: core_app.auth(core_app.user_token(customer))  # noqa: E731
    assert (await core_app.client.get(WHOAMI, headers=headers())).status_code == 200

    new_password = "rotated_" + "x" * 40
    admin = stack.cluster.admin_engine()
    try:
        async with admin.connect() as raw:
            conn = await raw.execution_options(isolation_level="AUTOCOMMIT")
            await conn.execute(text(f"ALTER ROLE \"{customer.db.app_role}\" PASSWORD '{new_password}'"))
    finally:
        await admin.dispose()
    await stack.pipeline_secrets.put(
        customer.db.app_secret_ref, {"username": customer.db.app_role, "password": new_password}
    )
    # Existing pooled connections are gone (as after a pooler restart); Core still holds the
    # old password in its cache.
    await core_app.runtime.router._pools[customer.id].engine.dispose()

    with caplog.at_level(logging.WARNING, logger="ims.db"):
        response = await core_app.client.get(WHOAMI, headers=headers())
    assert response.status_code == 200
    assert response.json()["db_user"] == customer.db.app_role
    assert any("credential rejected" in r.getMessage() for r in caplog.records), (
        "the old password must have been refused first, otherwise this proves nothing"
    )
