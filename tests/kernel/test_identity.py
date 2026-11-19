"""Identity and sessions through the real pipeline (LLD 6.1, 6.2, 6.3; LLD 17 "Identity" row).

Core talks to the real Platform Service (Login Directory, Licence Registry) in-process and to
real customer databases through the pooler. Users are created with the identity service, as the
access module's user endpoints (unit 3) and provisioning will.
"""

from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text

from ims_common import auth_codes as domain
from ims_common.clock import ManualClock
from ims_contracts.enums import LicenceModule
from ims_core.kernel.runtime import CoreRuntime
from ims_core.kernel.stages import PipelineStages
from ims_core.kernel.tenant_settings import TenantSettings
from ims_core.kernel.uow import unit_of_work
from ims_core.main import create_app
from ims_core.modules.identity import IdentityModule
from ims_core.modules.identity.public import CreatedUser, IdentityService, PrincipalStage
from ims_platform.registry import Actor, RegistryService
from ims_platform.runtime import PlatformRuntime
from tests.conftest import SwitchableTransport, new_core_runtime
from tests.support import probe
from tests.support.stack import Customer, Stack, onboard_customer

pytestmark = pytest.mark.db

PASSWORD = "correct horse battery staple"
OPERATOR = Actor("platform_user:test-operator")
WHOAMI = "/ui/v1/probe/whoami"


@dataclass
class Auth:
    app: FastAPI
    runtime: CoreRuntime
    client: httpx.AsyncClient
    identity: IdentityService
    clock: ManualClock

    async def post(self, path: str, body: dict[str, Any], **kwargs: Any) -> httpx.Response:
        return await self.client.post(f"/ui/v1/auth/{path}", json=body, **kwargs)

    async def create_user(self, customer: Customer, identifier: str, name: str = "Test User") -> CreatedUser:
        ctx = await self.runtime.credential_context(
            customer.id, module=LicenceModule.CORE, request_id="test-setup", source="system"
        )
        async with unit_of_work(self.runtime.router, ctx, self.clock) as uow:
            return await self.identity.create_user(uow, login_identifier=identifier, display_name=name)

    async def activated_user(self, customer: Customer, identifier: str) -> CreatedUser:
        created = await self.create_user(customer, identifier)
        response = await self.post(
            "activate",
            {
                "login_identifier": identifier,
                "activation_code": created.activation_code,
                "new_password": PASSWORD,
            },
        )
        assert response.status_code == 204, response.text
        return created

    def code(self, secret: str, *, offset: int = 0) -> str:
        raw = base64.b32decode(secret + "=" * (-len(secret) % 8))
        return domain.totp_code(raw, domain.totp_step(self.clock.now()) + offset)

    async def enrolled_session(self, identifier: str) -> tuple[dict[str, Any], str]:
        """First sign-in: password, enrolment, first code. Returns the session body and the secret."""
        login = await self.post("login", {"login_identifier": identifier, "password": PASSWORD})
        assert login.status_code == 200, login.text
        assert login.json()["status"] == "mfa_enrolment_required"
        challenge = login.json()["challenge_token"]
        enrol = await self.post("mfa/enrol", {"challenge_token": challenge})
        assert enrol.status_code == 200, enrol.text
        secret = enrol.json()["secret"]
        session = await self.post("mfa", {"challenge_token": challenge, "code": self.code(secret)})
        assert session.status_code == 200, session.text
        return session.json(), secret

    async def sign_in(self, identifier: str, secret: str) -> httpx.Response:
        """A later sign-in: password, then a code from the next time step (the last one is spent)."""
        self.clock.advance(seconds=30)
        login = await self.post("login", {"login_identifier": identifier, "password": PASSWORD})
        assert login.status_code == 200, login.text
        assert login.json()["status"] == "mfa_required"
        return await self.post(
            "mfa", {"challenge_token": login.json()["challenge_token"], "code": self.code(secret)}
        )

    async def whoami(self, access_token: str) -> httpx.Response:
        return await self.client.get(WHOAMI, headers={"Authorization": f"Bearer {access_token}"})


def _app(runtime: CoreRuntime) -> FastAPI:
    probe_state = probe.ProbeState()
    probe_stages = probe.stages(probe_state)
    stages = PipelineStages(
        principal=PrincipalStage(), rate_limit=probe_stages.rate_limit, authorise=probe_stages.authorise
    )
    app = create_app(
        runtime=runtime,
        stages=stages,
        routers=probe.build_routers(),
        modules=[IdentityModule()],
        run_change_feed=False,
    )
    app.state.probe = probe_state
    app.state.tenant_settings = TenantSettings(probe.REGISTRY, runtime.clock)
    return app


@pytest_asyncio.fixture
async def auth(core: CoreRuntime, clock: ManualClock) -> AsyncIterator[Auth]:
    app = _app(core)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://core") as client:
        yield Auth(app=app, runtime=core, client=client, identity=app.state.identity, clock=clock)


@pytest_asyncio.fixture
async def customer(
    stack: Stack, session_registry: RegistryService, clock: ManualClock, fresh_code: str
) -> Customer:
    return await onboard_customer(stack, session_registry, fresh_code, now=clock.now())


@pytest.fixture
def ident(fresh_code: str) -> str:
    return f"{fresh_code}.priya@zongovita.in"


def _problem(response: httpx.Response) -> tuple[int, str]:
    return response.status_code, response.json()["code"]


async def _owner_sql(stack: Stack, customer: Customer, sql: str, **params: Any) -> list[Any]:
    engine = await stack.migration_engine(customer.db)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(sql), params)
            return list(result.all()) if result.returns_rows else []
    finally:
        await engine.dispose()


# ------------------------------------------------------------------------------- happy path
async def test_activation_first_sign_in_and_mfa_enrolment_open_a_session(
    auth: Auth, stack: Stack, customer: Customer, ident: str
) -> None:
    created = await auth.create_user(customer, ident.upper(), name="Priya Sharma")
    rows = await _owner_sql(stack, customer, "SELECT login_identifier, status, password_hash FROM iam.users")
    assert [tuple(r) for r in rows] == [(ident, "invited", None)], "stored normalised, invited, no password"

    # The invited user cannot sign in yet.
    early = await auth.post("login", {"login_identifier": ident, "password": PASSWORD})
    assert _problem(early) == (401, "AUTH_REQUIRED")

    activated = await auth.post(
        "activate",
        {
            "login_identifier": ident,
            "activation_code": created.activation_code.lower(),
            "new_password": PASSWORD,
        },
    )
    assert activated.status_code == 204
    session, _secret = await auth.enrolled_session(ident)
    assert session["token_type"] == "Bearer"
    assert session["expires_in"] == 900
    assert len(session["recovery_codes"]) == 10, "recovery codes are shown once, at enrolment"

    who = await auth.whoami(session["access_token"])
    assert who.status_code == 200
    assert who.json()["customer_code"] == customer.code
    assert who.json()["principal_type"] == "user"

    audit = await _owner_sql(stack, customer, "SELECT action, actor_type FROM audit.audit_log ORDER BY seq")
    actions = [a for a, _ in audit]
    for expected in (
        "iam.user.created",
        "iam.user.activated",
        "iam.mfa.enrolment_started",
        "iam.mfa.enrolled",
        "iam.session.created",
    ):
        assert expected in actions
    stored = await _owner_sql(stack, customer, "SELECT secret_ciphertext FROM iam.mfa_factors")
    assert base64.b32decode(_secret + "=" * (-len(_secret) % 8)) not in bytes(stored[0][0]), (
        "secret encrypted at rest"
    )


async def test_mfa_is_required_on_every_sign_in_and_steps_cannot_be_replayed(
    auth: Auth, customer: Customer, ident: str
) -> None:
    await auth.activated_user(customer, ident)
    _session, secret = await auth.enrolled_session(ident)

    login = await auth.post("login", {"login_identifier": ident, "password": PASSWORD})
    assert login.json()["status"] == "mfa_required"
    assert "access_token" not in login.json(), "no token before the second factor"
    challenge = login.json()["challenge_token"]
    replay = await auth.post("mfa", {"challenge_token": challenge, "code": auth.code(secret)})
    assert _problem(replay) == (401, "MFA_INVALID"), "the step used at enrolment is spent"
    auth.clock.advance(seconds=30)
    ok = await auth.post("mfa", {"challenge_token": challenge, "code": auth.code(secret)})
    assert ok.status_code == 200
    again = await auth.post("mfa", {"challenge_token": challenge, "code": auth.code(secret, offset=1)})
    assert _problem(again) == (401, "AUTH_REQUIRED"), "a challenge is single use"


async def test_recovery_codes_work_once_each(auth: Auth, customer: Customer, ident: str) -> None:
    await auth.activated_user(customer, ident)
    session, _ = await auth.enrolled_session(ident)
    codes = session["recovery_codes"]

    async def with_recovery(code: str) -> httpx.Response:
        login = await auth.post("login", {"login_identifier": ident, "password": PASSWORD})
        return await auth.post(
            "mfa", {"challenge_token": login.json()["challenge_token"], "recovery_code": code}
        )

    assert (await with_recovery(codes[0].replace("-", " ").lower())).status_code == 200
    assert _problem(await with_recovery(codes[0])) == (401, "MFA_INVALID")
    assert (await with_recovery(codes[1])).status_code == 200


# ---------------------------------------------------------------------- constant-time login
async def test_every_sign_in_failure_looks_the_same_and_costs_one_verification(
    auth: Auth, customer: Customer, session_registry: RegistryService, ident: str, fresh_code: str
) -> None:
    """LD-80: unknown identifiers, wrong passwords, invited and suspended accounts are told apart
    neither by the answer nor by the work done."""
    await auth.activated_user(customer, ident)
    await auth.create_user(customer, f"{fresh_code}.invited@zongovita.in")
    attempts = [
        (ident, "wrong password entirely"),
        (f"{fresh_code}.nobody@zongovita.in", PASSWORD),
        (f"{fresh_code}.invited@zongovita.in", PASSWORD),
        ("not an identifier", PASSWORD),
    ]
    bodies = []
    for identifier, password in attempts:
        before = auth.identity.hasher.verifications
        response = await auth.post("login", {"login_identifier": identifier, "password": password})
        assert auth.identity.hasher.verifications - before == 1, identifier
        assert _problem(response) == (401, "AUTH_REQUIRED")
        assert response.headers["www-authenticate"] == "Bearer"
        body = response.json()
        body.pop("request_id")
        bodies.append(body)
    assert all(b == bodies[0] for b in bodies)
    assert bodies[0]["detail"] == "Sign-in failed"

    # A suspended customer's users get the same answer, after the same work. (The first poll only
    # finds the feed position; the suspension then arrives as a change notice.)
    await auth.runtime.snapshots.poll_changes_once()
    await session_registry.suspend_customer(customer.id, actor=OPERATOR, reason="test")
    await auth.runtime.snapshots.poll_changes_once()
    before = auth.identity.hasher.verifications
    response = await auth.post("login", {"login_identifier": ident, "password": PASSWORD})
    assert auth.identity.hasher.verifications - before == 1
    body = response.json()
    body.pop("request_id")
    assert (response.status_code, body) == (401, bodies[0])


async def test_five_failures_lock_the_account_for_fifteen_minutes(
    auth: Auth, stack: Stack, customer: Customer, ident: str
) -> None:
    await auth.activated_user(customer, ident)
    _, secret = await auth.enrolled_session(ident)
    for _ in range(5):
        wrong = await auth.post("login", {"login_identifier": ident, "password": "not the password at all"})
        assert _problem(wrong) == (401, "AUTH_REQUIRED")
    locked = await auth.post("login", {"login_identifier": ident, "password": PASSWORD})
    assert _problem(locked) == (401, "AUTH_REQUIRED"), "the right password does not help while locked"
    audit = await _owner_sql(
        stack, customer, "SELECT count(*) FROM audit.audit_log WHERE action = 'iam.user.locked'"
    )
    assert audit[0][0] == 1

    auth.clock.advance(seconds=15 * 60 - 31)
    assert _problem(await auth.post("login", {"login_identifier": ident, "password": PASSWORD})) == (
        401,
        "AUTH_REQUIRED",
    )
    auth.clock.advance(seconds=1)  # sign_in adds 30 s: exactly 15 minutes after the lock
    assert (await auth.sign_in(ident, secret)).status_code == 200, "unlocked after 15 minutes"


async def test_mfa_failures_count_toward_the_lockout(auth: Auth, customer: Customer, ident: str) -> None:
    await auth.activated_user(customer, ident)
    _, secret = await auth.enrolled_session(ident)
    login = await auth.post("login", {"login_identifier": ident, "password": PASSWORD})
    challenge = login.json()["challenge_token"]
    for _ in range(4):
        assert _problem(await auth.post("mfa", {"challenge_token": challenge, "code": "000000"})) == (
            401,
            "MFA_INVALID",
        )
    assert _problem(await auth.post("mfa", {"challenge_token": challenge, "code": "000000"})) == (
        401,
        "MFA_INVALID",
    )
    # Locked: the challenge died with the lock, and so does a fresh sign-in.
    auth.clock.advance(seconds=30)
    assert _problem(await auth.post("mfa", {"challenge_token": challenge, "code": auth.code(secret)})) == (
        401,
        "AUTH_REQUIRED",
    )
    assert _problem(await auth.post("login", {"login_identifier": ident, "password": PASSWORD})) == (
        401,
        "AUTH_REQUIRED",
    )


# ----------------------------------------------------------------------------- sessions
async def test_refresh_rotates_and_reusing_an_old_token_revokes_the_session(
    auth: Auth, stack: Stack, customer: Customer, ident: str
) -> None:
    await auth.activated_user(customer, ident)
    first, _ = await auth.enrolled_session(ident)
    second = await auth.post("refresh", {"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    assert second.json()["refresh_token"] != first["refresh_token"]
    assert (await auth.whoami(second.json()["access_token"])).status_code == 200

    stolen = await auth.post("refresh", {"refresh_token": first["refresh_token"]})
    assert _problem(stolen) == (401, "SESSION_REVOKED"), "an old refresh token signals theft"
    after = await auth.post("refresh", {"refresh_token": second.json()["refresh_token"]})
    assert _problem(after) == (401, "SESSION_REVOKED"), "the whole session is gone"
    assert _problem(await auth.whoami(second.json()["access_token"])) == (401, "SESSION_REVOKED")
    reasons = await _owner_sql(stack, customer, "SELECT revoke_reason FROM iam.sessions")
    assert [r for (r,) in reasons] == ["refresh_token_reuse"]


async def test_sessions_expire_after_eight_idle_hours_and_seven_days(
    auth: Auth, customer: Customer, ident: str
) -> None:
    await auth.activated_user(customer, ident)
    session, secret = await auth.enrolled_session(ident)
    auth.clock.advance(seconds=8 * 3600)
    assert _problem(await auth.post("refresh", {"refresh_token": session["refresh_token"]})) == (
        401,
        "AUTH_REQUIRED",
    )

    # Refreshing every 7 hours keeps a session alive until its absolute end.
    session = (await auth.sign_in(ident, secret)).json()
    for _ in range(23):
        auth.clock.advance(seconds=7 * 3600)
        refreshed = await auth.post("refresh", {"refresh_token": session["refresh_token"]})
        assert refreshed.status_code == 200
        session = refreshed.json()
    auth.clock.advance(seconds=7 * 3600)  # 168 h: past the 7-day absolute expiry
    assert _problem(await auth.post("refresh", {"refresh_token": session["refresh_token"]})) == (
        401,
        "AUTH_REQUIRED",
    )
    assert _problem(await auth.whoami(session["access_token"])) in {
        (401, "TOKEN_EXPIRED"),
        (401, "SESSION_REVOKED"),
    }


async def test_sign_out_revokes_the_session_and_is_idempotent(
    auth: Auth, customer: Customer, ident: str
) -> None:
    await auth.activated_user(customer, ident)
    session, _ = await auth.enrolled_session(ident)
    for _ in range(2):
        assert (await auth.post("logout", {"refresh_token": session["refresh_token"]})).status_code == 204
    assert (await auth.post("logout", {"refresh_token": "garbage"})).status_code == 204
    assert _problem(await auth.whoami(session["access_token"])) == (401, "SESSION_REVOKED")
    assert _problem(await auth.post("refresh", {"refresh_token": session["refresh_token"]})) == (
        401,
        "SESSION_REVOKED",
    )


async def test_principal_stage_refuses_inactive_users(
    auth: Auth, stack: Stack, customer: Customer, ident: str
) -> None:
    await auth.activated_user(customer, ident)
    session, _ = await auth.enrolled_session(ident)
    await _owner_sql(
        stack, customer, "UPDATE iam.users SET status = 'suspended' WHERE login_identifier = :i", i=ident
    )
    assert _problem(await auth.whoami(session["access_token"])) == (401, "PRINCIPAL_INACTIVE")
    assert _problem(await auth.post("refresh", {"refresh_token": session["refresh_token"]})) == (
        401,
        "PRINCIPAL_INACTIVE",
    )


async def test_tokens_of_one_customer_reach_only_that_customer(
    auth: Auth, stack: Stack, session_registry: RegistryService, clock: ManualClock, fresh_code: str
) -> None:
    first = await onboard_customer(stack, session_registry, f"{fresh_code}a", now=clock.now())
    second = await onboard_customer(stack, session_registry, f"{fresh_code}b", now=clock.now())
    a = await auth.activated_user(first, f"{fresh_code}.a@zongovita.in")
    await auth.activated_user(second, f"{fresh_code}.b@zongovita.in")
    session_a, _ = await auth.enrolled_session(f"{fresh_code}.a@zongovita.in")
    who = await auth.whoami(session_a["access_token"])
    assert who.json()["database"] == first.db.database_name
    # The same user and session IDs do not exist in the other customer's database.
    forged = auth.runtime.authenticator.issue_user_access(
        customer_id=second.id, user_id=a.user_id, session_id=UUID(int=0)
    )
    assert _problem(await auth.whoami(forged)) == (401, "SESSION_REVOKED")


# -------------------------------------------------------------------------------- activation
async def test_activation_rules(auth: Auth, customer: Customer, ident: str, fresh_code: str) -> None:
    created = await auth.create_user(customer, ident)
    weak = await auth.post(
        "activate",
        {
            "login_identifier": ident,
            "activation_code": created.activation_code,
            "new_password": "password1234",
        },
    )
    assert weak.status_code == 422
    assert weak.json()["errors"] == [{"field": "new_password", "message": "is too common"}]
    wrong = await auth.post(
        "activate", {"login_identifier": ident, "activation_code": "WRONG-CODE00", "new_password": PASSWORD}
    )
    assert _problem(wrong) == (401, "AUTH_REQUIRED")
    assert (
        await auth.post(
            "activate",
            {"login_identifier": ident, "activation_code": created.activation_code, "new_password": PASSWORD},
        )
    ).status_code == 204
    reused = await auth.post(
        "activate",
        {"login_identifier": ident, "activation_code": created.activation_code, "new_password": PASSWORD},
    )
    assert _problem(reused) == (401, "AUTH_REQUIRED"), "the code is single use"

    late = await auth.create_user(customer, f"{fresh_code}.late@zongovita.in")
    auth.clock.advance(seconds=72 * 3600)
    expired = await auth.post(
        "activate",
        {
            "login_identifier": f"{fresh_code}.late@zongovita.in",
            "activation_code": late.activation_code,
            "new_password": PASSWORD,
        },
    )
    assert _problem(expired) == (401, "AUTH_REQUIRED")


async def test_identifiers_are_unique_across_customers_and_users_count_against_the_licence(
    auth: Auth, stack: Stack, session_registry: RegistryService, clock: ManualClock, fresh_code: str
) -> None:
    first = await onboard_customer(stack, session_registry, f"{fresh_code}a", now=clock.now())
    second = await onboard_customer(stack, session_registry, f"{fresh_code}b", now=clock.now())
    await auth.create_user(first, f"{fresh_code}.dup@zongovita.in")
    with pytest.raises(Exception) as excinfo:
        await auth.create_user(second, f"{fresh_code}.DUP@ZongoVita.in")
    assert getattr(excinfo.value, "code", None) == "LOGIN_IDENTIFIER_TAKEN"
    rows = await _owner_sql(stack, second, "SELECT count(*) FROM iam.users")
    assert rows[0][0] == 0, "the refused user was not created"

    # The licence allows 200 users; fill it and the next one is refused.
    await _owner_sql(
        stack,
        first,
        "INSERT INTO iam.users (id, login_identifier, display_name, status) "
        "SELECT gen_random_uuid(), 'filler' || g || '@x.in', 'Filler', 'invited' FROM generate_series(1, 199) g",
    )
    with pytest.raises(Exception) as excinfo:
        await auth.create_user(first, f"{fresh_code}.over@zongovita.in")
    assert getattr(excinfo.value, "code", None) == "LIMIT_EXCEEDED"


# ------------------------------------------------------------------------------ directory
async def test_sign_in_survives_a_platform_service_outage(
    auth: Auth,
    stack: Stack,
    platform: PlatformRuntime,
    registry_link: SwitchableTransport,
    clock: ManualClock,
    customer: Customer,
    ident: str,
    fresh_code: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AD-79: cached directory entries at any age, then the signed bundle for a new process."""
    await auth.activated_user(customer, ident)
    _, secret = await auth.enrolled_session(ident)
    other = f"{fresh_code}.second@zongovita.in"
    await auth.activated_user(customer, other)
    await platform.bundle_publisher.publish_once()

    registry_link.down = True
    with caplog.at_level(logging.WARNING):
        clock.advance(seconds=3600)  # far past the 10-minute cache
        assert (await auth.sign_in(ident, secret)).status_code == 200

    fresh_runtime = await new_core_runtime(stack, clock, registry_link)  # a process started mid-outage
    app = _app(fresh_runtime)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://core"
        ) as client:
            login = await client.post(
                "/ui/v1/auth/login", json={"login_identifier": other, "password": PASSWORD}
            )
            assert login.status_code == 200, "resolved from the signed bundle"
            assert login.json()["status"] == "mfa_enrolment_required"
            unknown = await client.post(
                "/ui/v1/auth/login",
                json={"login_identifier": f"{fresh_code}.ghost@x.in", "password": PASSWORD},
            )
            assert _problem(unknown) == (401, "AUTH_REQUIRED")
    finally:
        await fresh_runtime.aclose()


async def test_an_identifier_taken_while_the_reservation_lapsed_suspends_the_user(
    auth: Auth,
    stack: Stack,
    platform: PlatformRuntime,
    session_registry: RegistryService,
    customer: Customer,
    fresh_code: str,
) -> None:
    """LLD 6.3 failure table: "Another customer took the identifier meanwhile"."""
    other = await session_registry.register_customer(
        code=f"{fresh_code}x", legal_name="Other", actor=OPERATOR
    )
    created = await auth.create_user(customer, f"{fresh_code}.lapsed@zongovita.in")
    # Simulate the lapse: the directory entry went back to reserved and expired, and another
    # customer's principal took it before this customer's activation ran.
    pepper_hash_sql = "UPDATE platform.login_directory SET status = 'reserved', reserved_until = now() - interval '1 minute' WHERE principal_id = :p"
    engine = stack.cluster.admin_engine("ims_control_plane")
    try:
        async with engine.begin() as conn:
            await conn.execute(text(pepper_hash_sql), {"p": created.user_id})
    finally:
        await engine.dispose()
    from ims_common.ids import uuid7  # noqa: PLC0415

    await platform.directory.reserve(
        customer_id=other,
        principal_type="user",
        principal_id=uuid7(),
        identifier=f"{fresh_code}.lapsed@zongovita.in",
        actor=OPERATOR,
    )
    ctx = await auth.runtime.credential_context(
        customer.id, module=LicenceModule.CORE, request_id="t", source="worker"
    )
    from ims_contracts.enums import PrincipalType  # noqa: PLC0415

    await auth.identity.activate_directory_entry(
        ctx, PrincipalType.USER, created.user_id, f"{fresh_code}.lapsed@zongovita.in"
    )
    rows = await _owner_sql(
        stack,
        customer,
        "SELECT u.status, a.reason FROM iam.users u JOIN audit.audit_log a ON a.entity_id = u.id::text "
        "WHERE u.id = :id AND a.action = 'iam.user.suspended'",
        id=created.user_id,
    )
    assert [tuple(r) for r in rows] == [("suspended", "identifier in use")]


# ----------------------------------------------------------------------------- API clients
async def test_client_credentials_grant(auth: Auth, stack: Stack, customer: Customer) -> None:
    ctx = await auth.runtime.credential_context(
        customer.id, module=LicenceModule.CORE, request_id="t", source="system"
    )
    async with unit_of_work(auth.runtime.router, ctx, auth.clock) as uow:
        created = await auth.identity.create_api_client(uow, name="Asset Maintenance connector")
    client_id, secret = str(created.client_id), created.client_secret

    form = await auth.client.post(
        "/api/v1/oauth/token",
        data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret},
    )
    assert form.status_code == 200, form.text
    assert form.headers["cache-control"] == "no-store"
    assert (form.json()["token_type"], form.json()["expires_in"]) == ("Bearer", 600)
    who = await auth.client.get(
        "/api/v1/probe/whoami", headers={"Authorization": f"Bearer {form.json()['access_token']}"}
    )
    assert who.json() == {"customer_code": customer.code, "principal_type": "api_client"}

    basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    via_basic = await auth.client.post(
        "/api/v1/oauth/token",
        data={"grant_type": "client_credentials"},
        headers={"Authorization": f"Basic {basic}"},
    )
    assert via_basic.status_code == 200

    for data in (
        {"grant_type": "client_credentials", "client_id": client_id, "client_secret": "wrong"},
        {
            "grant_type": "client_credentials",
            "client_id": "00000000-0000-7000-8000-000000000000",
            "client_secret": secret,
        },
    ):
        refused = await auth.client.post("/api/v1/oauth/token", data=data)
        assert _problem(refused) == (401, "AUTH_REQUIRED")
    unsupported = await auth.client.post(
        "/api/v1/oauth/token", data={"grant_type": "password", "client_id": client_id}
    )
    assert _problem(unsupported) == (400, "VALIDATION_FAILED")

    await _owner_sql(
        stack, customer, "UPDATE iam.api_clients SET status = 'disabled' WHERE id = :id", id=created.client_id
    )
    assert _problem(
        await auth.client.post(
            "/api/v1/oauth/token",
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret},
        )
    ) == (401, "AUTH_REQUIRED")
    assert _problem(
        await auth.client.get(
            "/api/v1/probe/whoami", headers={"Authorization": f"Bearer {form.json()['access_token']}"}
        )
    ) == (401, "PRINCIPAL_INACTIVE")


async def test_user_tokens_and_api_tokens_do_not_cross_audiences(
    auth: Auth, customer: Customer, ident: str
) -> None:
    await auth.activated_user(customer, ident)
    session, _ = await auth.enrolled_session(ident)
    as_api = await auth.client.get(
        "/api/v1/probe/whoami", headers={"Authorization": f"Bearer {session['access_token']}"}
    )
    assert _problem(as_api) == (401, "AUTH_REQUIRED")
    as_refresh = await auth.client.get(
        WHOAMI, headers={"Authorization": f"Bearer {session['refresh_token']}"}
    )
    assert _problem(as_refresh) == (401, "AUTH_REQUIRED"), "a refresh token is not an access token"
    timed_out = timedelta(minutes=15)
    auth.clock.advance(seconds=timed_out.total_seconds())
    assert _problem(await auth.whoami(session["access_token"])) == (401, "TOKEN_EXPIRED")
