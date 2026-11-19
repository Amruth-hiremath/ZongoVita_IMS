"""Platform administration through the Platform Service's /platform/v1 (LLD 4, 6.2, 6.4, 6.8, 15;
AD-04, AD-13, AD-23, AD-78).

Staff sign in for real (Argon2id password, TOTP). Customers are onboarded through the real
database pipeline and Registry. Every assertion goes through HTTP.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text

from ims_common.clock import ManualClock
from ims_core.kernel.runtime import CoreRuntime
from ims_platform.accounts import StaffRole
from ims_platform.registry import RegistryService
from tests.support.platform import CHEAP_HASHER, PASSWORD, Console, console_for
from tests.support.stack import Stack, onboard_customer
from tests.support.tenant import full_app

pytestmark = pytest.mark.db


@pytest_asyncio.fixture
async def console(stack: Stack, clock: ManualClock, core: CoreRuntime) -> AsyncIterator[Console]:
    async with console_for(stack, clock, core, full_app(core)) as c:
        yield c


def _problem(response: httpx.Response) -> tuple[int, str]:
    return response.status_code, response.json()["code"]


async def _count(stack: Stack, sql: str, **params: Any) -> int:
    engine = stack.cluster.admin_engine("ims_control_plane")
    try:
        async with engine.connect() as conn:
            return int((await conn.execute(text(sql), params)).scalar_one())
    finally:
        await engine.dispose()


# ----------------------------------------------------------------------------- staff sign-in
async def test_staff_sign_in_needs_the_password_then_an_authenticator_code(
    console: Console, fresh_code: str
) -> None:
    admin = await console.staff(f"{fresh_code}.kiran@zongovita.test")
    me = await console.call("GET", "/me", admin)
    assert me.status_code == 200, me.text
    assert (me.json()["role"], me.json()["display_name"]) == ("system_admin", "Kiran Desai")

    # Every failure is the same generic 401 after exactly one Argon2id verification (LD-80).
    for identifier, password in (
        (admin.identifier, "wrong password entirely"),
        (f"{fresh_code}.nobody@zongovita.test", PASSWORD),
        ("not an identifier", PASSWORD),
    ):
        before = CHEAP_HASHER.verifications
        refused = await console.client.post(
            "/platform/v1/auth/login", json={"login_identifier": identifier, "password": password}
        )
        assert _problem(refused) == (401, "AUTH_REQUIRED")
        assert refused.json()["detail"] == "Sign-in failed"
        assert CHEAP_HASHER.verifications - before == 1

    # A later sign-in asks for a code; the step used at enrolment cannot be replayed (LD-79).
    login = await console.client.post(
        "/platform/v1/auth/login", json={"login_identifier": admin.identifier, "password": PASSWORD}
    )
    assert login.json()["status"] == "mfa_required"
    replay = await console.client.post(
        "/platform/v1/auth/mfa",
        json={"challenge_token": login.json()["challenge_token"], "code": console.code(admin.secret)},
    )
    assert _problem(replay) == (401, "MFA_INVALID")
    console.clock.advance(seconds=30)
    fresh = await console.client.post(
        "/platform/v1/auth/mfa",
        json={"challenge_token": login.json()["challenge_token"], "code": console.code(admin.secret)},
    )
    assert fresh.status_code == 200, fresh.text


async def test_platform_tokens_are_not_core_tokens_and_core_tokens_are_not_platform_tokens(
    console: Console, core: CoreRuntime, fresh_code: str, stack: Stack, session_registry: RegistryService
) -> None:
    """LLD 6.2: platform tokens carry a different issuer and audience; Core rejects them."""
    admin = await console.staff(f"{fresh_code}.kiran@zongovita.test")
    core_app = full_app(core)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=core_app), base_url="http://core"
    ) as client:
        assert _problem(await client.get("/ui/v1/me", headers=admin.headers)) == (401, "AUTH_REQUIRED")
    customer = await onboard_customer(stack, session_registry, fresh_code, now=console.clock.now())
    core_token = core.authenticator.issue_user_access(
        customer_id=customer.id, user_id=admin.user_id, session_id=admin.user_id
    )
    assert _problem(
        await console.call("GET", "/me", None, headers={"Authorization": f"Bearer {core_token}"})
    ) == (401, "AUTH_REQUIRED")


async def test_lockout_refresh_rotation_and_deactivation(console: Console, fresh_code: str) -> None:
    admin = await console.staff(f"{fresh_code}.kiran@zongovita.test")
    engineer = await console.staff(
        f"{fresh_code}.ravi@zongovita.test", StaffRole.SUPPORT_ENGINEER, name="Ravi Kumar"
    )

    # Refresh rotates; presenting the old refresh token revokes the session (LD-26).
    rotated = await console.client.post(
        "/platform/v1/auth/refresh", json={"refresh_token": engineer.refresh_token}
    )
    assert rotated.status_code == 200, rotated.text
    reused = await console.client.post(
        "/platform/v1/auth/refresh", json={"refresh_token": engineer.refresh_token}
    )
    assert _problem(reused) == (401, "SESSION_REVOKED")
    assert _problem(
        await console.call(
            "GET", "/me", None, headers={"Authorization": f"Bearer {rotated.json()['access_token']}"}
        )
    ) == (401, "SESSION_REVOKED")

    # Deactivation ends the person's sessions at once.
    signed_in = await console.staff(
        f"{fresh_code}.sita@zongovita.test", StaffRole.SUPPORT_ENGINEER, name="Sita R"
    )
    gone = await console.call(
        "POST", f"/users/{signed_in.user_id}/deactivate", admin, json={"reason": "left"}
    )
    assert gone.json()["status"] == "deactivated"
    assert _problem(await console.call("GET", "/me", signed_in)) == (401, "SESSION_REVOKED")

    # Five wrong passwords lock the account for 15 minutes; the right one is refused meanwhile.
    for _ in range(5):
        await console.client.post(
            "/platform/v1/auth/login",
            json={"login_identifier": engineer.identifier, "password": "wrong password!!"},
        )
    right = {"login_identifier": engineer.identifier, "password": PASSWORD}
    assert _problem(await console.client.post("/platform/v1/auth/login", json=right)) == (
        401,
        "AUTH_REQUIRED",
    )
    console.clock.advance(seconds=15 * 60)
    assert (await console.client.post("/platform/v1/auth/login", json=right)).status_code == 200


async def test_staff_roles(console: Console, fresh_code: str) -> None:
    """HLD 3: system admins administer; support engineers have no administration rights."""
    engineer = await console.staff(
        f"{fresh_code}.ravi@zongovita.test", StaffRole.SUPPORT_ENGINEER, name="Ravi Kumar"
    )
    assert (await console.call("GET", "/me", engineer)).json()["role"] == "support_engineer"
    for method, path in (
        ("GET", "/customers"),
        ("GET", "/provisioning-runs"),
        ("GET", "/users"),
        ("GET", "/audit"),
        ("POST", "/users"),
    ):
        response = await console.call(method, path, engineer, json={} if method == "POST" else None)
        assert _problem(response) in ((403, "PERMISSION_DENIED"), (422, "VALIDATION_FAILED")), path
        if method == "GET":
            assert _problem(response) == (403, "PERMISSION_DENIED"), path
    assert _problem(await console.call("GET", "/customers", None)) == (401, "AUTH_REQUIRED")


async def test_staff_accounts_are_created_by_system_admins(console: Console, fresh_code: str) -> None:
    admin = await console.staff(f"{fresh_code}.kiran@zongovita.test")
    created = await console.call(
        "POST",
        "/users",
        admin,
        json={
            "login_identifier": f"{fresh_code}.NEW@ZongoVita.test ",
            "display_name": "New",
            "role": "support_engineer",
        },
    )
    assert created.status_code == 201, created.text
    assert created.headers["cache-control"] == "no-store"
    assert created.json()["user"]["login_identifier"] == f"{fresh_code}.new@zongovita.test"
    assert created.json()["user"]["status"] == "invited"
    duplicate = await console.call(
        "POST",
        "/users",
        admin,
        json={
            "login_identifier": f"{fresh_code}.new@zongovita.test",
            "display_name": "X",
            "role": "system_admin",
        },
    )
    assert _problem(duplicate) == (422, "VALIDATION_FAILED")
    listed = await console.call("GET", "/users", admin)
    assert f"{fresh_code}.new@zongovita.test" in {u["login_identifier"] for u in listed.json()["items"]}


# --------------------------------------------------------------------- customers and licences
async def test_customers_licences_and_licence_state(
    console: Console, stack: Stack, session_registry: RegistryService, fresh_code: str
) -> None:
    admin = await console.staff(f"{fresh_code}.kiran@zongovita.test")
    customer = await onboard_customer(
        stack, session_registry, fresh_code, now=console.clock.now(), valid_for_days=30, grace_days=14
    )
    listed = await console.call("GET", "/customers", admin)
    row = next(c for c in listed.json()["items"] if c["code"] == fresh_code)
    assert (row["status"], row["licence_state"], row["licence"]["record_status"]) == (
        "active",
        "active",
        "active",
    )
    assert row["database"]["status"] == "ready" and row["database"]["database_name"] == f"ims_c_{fresh_code}"

    # Licence state is derived, never stored (LLD 6.4): grace starts at the end date.
    console.clock.set(customer.valid_until + timedelta(days=1))
    admin = await console.sign_in_again(admin)  # the earlier session has expired meanwhile
    grace = (await console.call("GET", f"/customers/{customer.id}", admin)).json()
    assert grace["licence_state"] == "grace"
    assert grace["grace_ends_at"] is not None

    # Renewal: a new draft licence, activated, supersedes the old one.
    now = console.clock.now()
    draft = await console.call(
        "POST",
        f"/customers/{customer.id}/licences",
        admin,
        json={
            "licence_no": f"LIC-{fresh_code}-2",
            "valid_from": now.isoformat(),
            "valid_until": (now + timedelta(days=365)).isoformat(),
            "max_sites": 8,
            "max_users": 300,
            "modules": ["ims.core", "ims.integration"],
        },
    )
    assert draft.status_code == 201, draft.text
    assert draft.json()["record_status"] == "draft"
    renewed = await console.call("POST", f"/licences/{draft.json()['id']}/activate", admin)
    assert renewed.json()["licence_state"] == "active"
    assert renewed.json()["licence"]["max_users"] == 300
    history = (await console.call("GET", f"/customers/{customer.id}/licences", admin)).json()["items"]
    assert sorted(item["record_status"] for item in history) == ["active", "superseded"]

    # Suspension and reinstatement are ZongoVita actions with a reason (AD-78).
    assert _problem(await console.call("POST", f"/customers/{customer.id}/suspend", admin, json={})) == (
        422,
        "VALIDATION_FAILED",
    )
    suspended = await console.call(
        "POST", f"/customers/{customer.id}/suspend", admin, json={"reason": "unpaid"}
    )
    assert (suspended.json()["status"], suspended.json()["licence_state"]) == ("suspended", "suspended")
    reinstated = await console.call(
        "POST", f"/customers/{customer.id}/reinstate", admin, json={"reason": "paid"}
    )
    assert reinstated.json()["licence_state"] == "active"

    audit = (await console.call("GET", "/audit", admin, params={"customer_id": str(customer.id)})).json()[
        "items"
    ]
    mine = {entry["action"] for entry in audit if entry["actor"] == f"platform_user:{admin.user_id}"}
    assert {"customer.suspended", "customer.reinstated"} <= mine, mine
    changes = await _count(
        stack, "SELECT count(*) FROM platform.change_feed WHERE customer_id = :id", id=customer.id
    )
    assert changes >= 4, "every change is announced on the change feed"


async def test_two_admins_racing_on_one_customer_leave_a_consistent_state(
    console: Console, stack: Stack, session_registry: RegistryService, fresh_code: str
) -> None:
    admin = await console.staff(f"{fresh_code}.kiran@zongovita.test")
    customer = await onboard_customer(stack, session_registry, fresh_code, now=console.clock.now())
    results = await asyncio.gather(
        console.call("POST", f"/customers/{customer.id}/suspend", admin, json={"reason": "a"}),
        console.call("POST", f"/customers/{customer.id}/suspend", admin, json={"reason": "b"}),
    )
    assert sorted(r.status_code for r in results) == [200, 409]
