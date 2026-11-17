"""Access control through the real pipeline (LLD 5.1, 6.1 steps 7 and 8, section 7, 12).

Every request here is a real HTTP request to the full Core application: real tokens from real
sign-ins (password and TOTP), the licence gate, the customer's database through the pooler, the
principal, rate-limit and authorise stages, idempotency, audit. Users are created through the
user endpoints; the super admin as provisioning creates it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text

from ims_common.clock import ManualClock
from ims_common.ids import uuid7
from ims_contracts.enums import LicenceModule
from ims_contracts.permissions import ALL_CODES, RESERVED_TO_SUPER_ADMIN, SEEDED_BY_CODE
from ims_core.kernel.authn import AUDIENCE_API, AUDIENCE_UI
from ims_core.kernel.routes import ImsRouter, Permission, Uow, declare
from ims_core.kernel.runtime import CoreRuntime
from ims_core.modules.access.public import RateLimits
from ims_platform.registry import RegistryService
from tests.support.stack import Customer, Stack, onboard_customer
from tests.support.tenant import Tenant, full_app

pytestmark = pytest.mark.db

SITE_A = UUID("018f6f2a-0000-7000-8000-0000000000a1")
SITE_B = UUID("018f6f2a-0000-7000-8000-0000000000b2")


# --------------------------------------------------------------- routes used only by tests
def _test_routers() -> list[ImsRouter]:
    """A command on a record at a site (the record's site comes from the path here, standing in
    for a loaded record), and two public-API routes for API-client permissions."""
    ui = ImsRouter(prefix="/ui/v1/test", audience=AUDIENCE_UI, module=LicenceModule.CORE)
    api = ImsRouter(prefix="/api/v1/test", audience=AUDIENCE_API, module=LicenceModule.INTEGRATION)

    @ui.get("/stock-at/{site_id}")
    @declare(access=Permission("inventory.stock.view"), read_only_ok=True)
    async def stock_at(site_id: UUID, uow: Uow) -> dict[str, Any]:
        uow.grants.require_site("inventory.stock.view", site_id)
        return {"ok": True}

    @api.get("/stock-levels")
    @declare(access=Permission("inventory.stock.view"), read_only_ok=True)
    async def stock_levels(uow: Uow) -> dict[str, Any]:
        return {"ok": True}

    @api.post("/items")
    @declare(access=Permission("catalog.item.create"), read_only_ok=False)
    async def create_item(uow: Uow) -> dict[str, Any]:
        return {"ok": True}

    return [ui, api]


async def _tenant(
    stack: Stack,
    registry: RegistryService,
    core: CoreRuntime,
    clock: ManualClock,
    code: str,
    *,
    limits: RateLimits | None = None,
    **onboarding: Any,
) -> AsyncIterator[Tenant]:
    customer = await onboard_customer(stack, registry, code, now=clock.now(), **onboarding)
    app = full_app(core, limits=limits, routers=_test_routers())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://core") as client:
        tenant = Tenant(app=app, client=client, runtime=core, clock=clock, customer=customer)
        await tenant.bootstrap_super_admin(f"{code}.admin@zongovita.in")
        yield tenant


@pytest_asyncio.fixture
async def tenant(
    stack: Stack, session_registry: RegistryService, core: CoreRuntime, clock: ManualClock, fresh_code: str
) -> AsyncIterator[Tenant]:
    async for t in _tenant(stack, session_registry, core, clock, fresh_code):
        yield t


def _problem(response: httpx.Response) -> tuple[int, str]:
    return response.status_code, response.json()["code"]


async def _sql(stack: Stack, customer: Customer, sql: str, **params: Any) -> list[Any]:
    engine = await stack.migration_engine(customer.db)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(sql), params)
            return list(result.all()) if result.returns_rows else []
    finally:
        await engine.dispose()


def _perms(me: dict[str, Any]) -> dict[str, list[str] | None]:
    return {p["code"]: p["site_ids"] for p in me["permissions"]}


# ------------------------------------------------------------------------------------- /me
async def test_me_reports_effective_permissions_per_site_and_the_licence(tenant: Tenant) -> None:
    admin = tenant.super_admin
    assert admin is not None
    me = await tenant.get("/ui/v1/me", admin)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["is_super_admin"] is True
    assert body["user_type_no"] == 1
    assert body["role_label"] == "Super Admin · Type 1"
    assert _perms(body) == dict.fromkeys(ALL_CODES), "the super admin holds everything everywhere"
    assert body["licence"]["state"] == "active"
    assert body["licence"]["grace_ends_at"] is None
    assert set(body["licence"]["modules"]) == {m.value for m in LicenceModule}
    assert body["unread_notifications"] is None

    store = await tenant.create_person(
        f"{tenant.customer.code}.store@zongovita.in", [("user_type_3", str(SITE_A))], name="Suresh Patil"
    )
    mine = (await tenant.get("/ui/v1/me", store)).json()
    assert mine["is_super_admin"] is False
    assert mine["role_label"] == "User Type 3"
    perms = _perms(mine)
    assert set(perms) == SEEDED_BY_CODE["user_type_3"].permissions
    assert perms["inventory.stock.view"] == [str(SITE_A)], "site-scoped: only where assigned"
    assert perms["catalog.item.view"] is None, "not site-scoped: everywhere"


# ------------------------------------------------------------------- step 8: the gate
async def test_declared_permission_and_site_scope_are_enforced(tenant: Tenant) -> None:
    code = tenant.customer.code
    store = await tenant.create_person(f"{code}.store@zongovita.in", [("user_type_3", str(SITE_A))])
    requester = await tenant.create_person(f"{code}.req@zongovita.in", [("user_type_4", None)])

    assert _problem(await tenant.get("/ui/v1/users", requester)) == (403, "PERMISSION_DENIED")
    assert _problem(await tenant.get("/ui/v1/roles", store)) == (403, "PERMISSION_DENIED")
    assert (await tenant.get("/ui/v1/me", requester)).status_code == 200, (
        "authenticated routes need no permission"
    )

    # The record's site decides, not where else the caller holds the permission.
    assert (await tenant.get(f"/ui/v1/test/stock-at/{SITE_A}", store)).status_code == 200
    assert _problem(await tenant.get(f"/ui/v1/test/stock-at/{SITE_B}", store)) == (403, "SITE_SCOPE_DENIED")
    assert _problem(await tenant.get(f"/ui/v1/test/stock-at/{SITE_A}", requester)) == (
        403,
        "PERMISSION_DENIED",
    )
    admin = tenant.super_admin
    assert admin is not None
    assert (await tenant.get(f"/ui/v1/test/stock-at/{SITE_B}", admin)).status_code == 200


# --------------------------------------------------------------------------------- users
async def test_user_lifecycle_through_the_endpoints(tenant: Tenant, stack: Stack) -> None:
    admin = tenant.super_admin
    assert admin is not None
    code = tenant.customer.code
    created = await tenant.post(
        "/ui/v1/users",
        admin,
        {
            "login_identifier": f"  {code}.Priya@ZongoVita.in ",
            "display_name": "Priya Sharma",
            "email": "priya@example.test",
            "assignments": [{"role_id": tenant.role_id("user_type_2"), "site_id": None}],
        },
    )
    assert created.status_code == 201, created.text
    assert created.headers["cache-control"] == "no-store"
    body = created.json()
    user = body["user"]
    assert user["status"] == "invited"
    assert user["login_identifier"] == f"{code}.priya@zongovita.in"
    assert [a["role_code"] for a in user["assignments"]] == ["user_type_2"]
    assert len(body["activation_code"].replace("-", "")) == 12, "D-14: 12 characters, shown grouped"

    listed = await tenant.get("/ui/v1/users", admin, params={"q": "priya"})
    assert [u["display_name"] for u in listed.json()["items"]] == ["Priya Sharma"]
    page = await tenant.get("/ui/v1/users", admin, params={"limit": 1})
    assert len(page.json()["items"]) == 1 and page.json()["next_cursor"]
    rest = await tenant.get("/ui/v1/users", admin, params={"limit": 1, "cursor": page.json()["next_cursor"]})
    assert rest.json()["items"][0]["id"] != page.json()["items"][0]["id"]

    # Master-data edit: If-Match required, then checked.
    one = await tenant.get(f"/ui/v1/users/{user['id']}", admin)
    etag = one.headers["etag"]
    path = f"/ui/v1/users/{user['id']}"
    edit = {"display_name": "Priya S.", "email": None}
    assert _problem(await tenant.call("PATCH", path, admin, json=edit)) == (428, "PRECONDITION_REQUIRED")
    stale = await tenant.call("PATCH", path, admin, json=edit, headers={"If-Match": '"999"'})
    assert _problem(stale) == (412, "VERSION_CONFLICT")
    done = await tenant.call("PATCH", path, admin, json=edit, headers={"If-Match": etag})
    assert done.status_code == 200, done.text
    assert done.json()["display_name"] == "Priya S."
    assert done.headers["etag"] != etag

    # Deactivation ends sessions now and frees the licence seat.
    priya = await tenant.activate_and_enrol(
        UUID(user["id"]), f"{code}.priya@zongovita.in", body["activation_code"]
    )
    assert (await tenant.get("/ui/v1/me", priya)).status_code == 200
    gone = await tenant.post(f"/ui/v1/users/{user['id']}/deactivate", admin, {"reason": "left the company"})
    assert gone.status_code == 200, gone.text
    assert gone.json()["status"] == "deactivated"
    assert _problem(await tenant.get("/ui/v1/me", priya)) == (401, "SESSION_REVOKED")
    again = await tenant.post(f"/ui/v1/users/{user['id']}/deactivate", admin, {})
    assert _problem(again) == (409, "INVALID_STATE_TRANSITION")

    audit = await _sql(stack, tenant.customer, "SELECT action FROM audit.audit_log ORDER BY seq")
    actions = [a for (a,) in audit]
    for expected in (
        "iam.user.created",
        "iam.role_assignment.granted",
        "iam.user.updated",
        "iam.user.deactivated",
    ):
        assert expected in actions


async def test_a_customers_users_are_invisible_to_another_customer(
    tenant: Tenant, stack: Stack, session_registry: RegistryService, core: CoreRuntime, clock: ManualClock
) -> None:
    """LLD 17 "Tenant isolation": customer A's token with customer B's IDs returns 404."""
    other_admin = tenant.super_admin
    assert other_admin is not None
    async for other in _tenant(stack, session_registry, core, clock, f"{tenant.customer.code}x"):
        assert other.super_admin is not None
        theirs = other.super_admin.user_id
        assert _problem(await tenant.get(f"/ui/v1/users/{theirs}", other_admin)) == (404, "NOT_FOUND")
        listed = await tenant.get("/ui/v1/users", other_admin)
        assert str(theirs) not in {u["id"] for u in listed.json()["items"]}


# ------------------------------------------------------------------- no self-escalation
async def test_managers_cannot_grant_what_they_do_not_hold(tenant: Tenant) -> None:
    admin = tenant.super_admin
    assert admin is not None
    code = tenant.customer.code
    user_admin_role = await tenant.post(
        "/ui/v1/roles",
        admin,
        {"name": "Site user admin", "permissions": ["access.user.manage", "issuance.request.create"]},
    )
    assert user_admin_role.status_code == 201, user_admin_role.text
    raiser_role = await tenant.post(
        "/ui/v1/roles", admin, {"name": "Raiser", "permissions": ["issuance.request.create"]}
    )
    await tenant.refresh_roles()
    site_admin = await tenant.create_person(
        f"{code}.siteadmin@zongovita.in", [("site_user_admin", str(SITE_A))]
    )
    target = await tenant.create_person(f"{code}.target@zongovita.in", [])

    def assign(role_id: str, site: UUID | None) -> dict[str, Any]:
        return {
            "principal_type": "user",
            "principal_id": str(target.user_id),
            "role_id": role_id,
            "site_id": str(site) if site else None,
        }

    raiser = raiser_role.json()["id"]
    # Type 4 includes returns.return.create, which the site admin does not hold.
    denied = await tenant.post(
        "/ui/v1/role-assignments", site_admin, assign(tenant.role_id("user_type_4"), SITE_A)
    )
    assert _problem(denied) == (403, "PERMISSION_DENIED")
    # Held at site A only: not at site B, and not "every site".
    assert _problem(await tenant.post("/ui/v1/role-assignments", site_admin, assign(raiser, SITE_B))) == (
        403,
        "SITE_SCOPE_DENIED",
    )
    assert _problem(await tenant.post("/ui/v1/role-assignments", site_admin, assign(raiser, None))) == (
        403,
        "SITE_SCOPE_DENIED",
    )
    granted = await tenant.post("/ui/v1/role-assignments", site_admin, assign(raiser, SITE_A))
    assert granted.status_code == 201, granted.text
    duplicate = await tenant.post("/ui/v1/role-assignments", site_admin, assign(raiser, SITE_A))
    assert _problem(duplicate) == (409, "INVALID_STATE_TRANSITION")

    # A role manager cannot add a permission they lack to any role.
    role_admin_role = await tenant.post(
        "/ui/v1/roles",
        admin,
        {"name": "Role admin", "permissions": ["access.role.manage", "catalog.item.view"]},
    )
    await tenant.refresh_roles()
    role_admin = await tenant.create_person(f"{code}.roleadmin@zongovita.in", [("role_admin", None)])
    raiser_now = await tenant.get(f"/ui/v1/roles/{raiser}", role_admin)
    put = f"/ui/v1/roles/{raiser}/permissions"
    escalate = await tenant.call(
        "PUT",
        put,
        role_admin,
        json={"permissions": ["issuance.request.create", "catalog.item.create"]},
        headers={"If-Match": raiser_now.headers["etag"]},
    )
    assert _problem(escalate) == (403, "PERMISSION_DENIED")
    allowed = await tenant.call(
        "PUT",
        put,
        role_admin,
        json={"permissions": ["issuance.request.create", "catalog.item.view"]},
        headers={"If-Match": raiser_now.headers["etag"]},
    )
    assert allowed.status_code == 200, allowed.text
    assert role_admin_role.status_code == 201


# ---------------------------------------------------------------- the super admin's rules
async def test_super_admin_role_and_holder_are_protected(tenant: Tenant) -> None:
    admin = tenant.super_admin
    assert admin is not None
    code = tenant.customer.code
    other_admin = await tenant.create_person(f"{code}.type1@zongovita.in", [("user_type_1", None)])
    super_role = tenant.roles["super_admin"]
    assert super_role["editable"] is False
    assert set(super_role["permissions"]) == ALL_CODES

    via_generic = await tenant.post(
        "/ui/v1/role-assignments",
        admin,
        {"principal_type": "user", "principal_id": str(other_admin.user_id), "role_id": super_role["id"]},
    )
    assert _problem(via_generic) == (403, "PERMISSION_DENIED")
    perms = await tenant.call(
        "PUT",
        f"/ui/v1/roles/{super_role['id']}/permissions",
        admin,
        json={"permissions": []},
        headers={"If-Match": f'"{super_role["version"]}"'},
    )
    assert _problem(perms) == (403, "PERMISSION_DENIED")
    reserved = await tenant.post(
        "/ui/v1/roles", admin, {"name": "Sneaky", "permissions": sorted(RESERVED_TO_SUPER_ADMIN)[:1]}
    )
    assert _problem(reserved) == (422, "VALIDATION_FAILED")

    # Type 1 holds access.user.manage but cannot touch the super admin.
    me = (await tenant.get(f"/ui/v1/users/{admin.user_id}", admin)).json()
    held = next(a for a in me["assignments"] if a["super_admin"])
    assert _problem(await tenant.post(f"/ui/v1/role-assignments/{held['id']}/revoke", other_admin, {})) == (
        403,
        "PERMISSION_DENIED",
    )
    assert _problem(await tenant.post(f"/ui/v1/users/{admin.user_id}/deactivate", other_admin, {})) == (
        403,
        "PERMISSION_DENIED",
    )
    etag = (await tenant.get(f"/ui/v1/users/{admin.user_id}", admin)).headers["etag"]
    edit = {"display_name": "Someone else", "email": None}
    path = f"/ui/v1/users/{admin.user_id}"
    assert _problem(await tenant.call("PATCH", path, other_admin, json=edit, headers={"If-Match": etag})) == (
        403,
        "PERMISSION_DENIED",
    )
    own = await tenant.call(
        "PATCH", path, admin, json={"display_name": "Arjun M.", "email": None}, headers={"If-Match": etag}
    )
    assert own.status_code == 200, "the super admin may edit their own profile"
    # Not even the super admin can deactivate or demote themself without a transfer.
    assert _problem(await tenant.post(f"/ui/v1/users/{admin.user_id}/deactivate", admin, {})) == (
        403,
        "PERMISSION_DENIED",
    )
    assert _problem(await tenant.post(f"/ui/v1/role-assignments/{held['id']}/revoke", admin, {})) == (
        403,
        "PERMISSION_DENIED",
    )
    # Reserved permissions: only the super admin holds them.
    transfer = await tenant.post(
        "/ui/v1/super-admin/transfer", other_admin, {"user_id": str(other_admin.user_id)}
    )
    assert _problem(transfer) == (403, "PERMISSION_DENIED")


async def test_super_admin_transfer_moves_the_role_and_concurrent_transfers_leave_exactly_one(
    tenant: Tenant, stack: Stack
) -> None:
    admin = tenant.super_admin
    assert admin is not None
    code = tenant.customer.code
    b = await tenant.create_person(f"{code}.b@zongovita.in", [("user_type_1", None)], name="B")
    c = await tenant.create_person(f"{code}.c@zongovita.in", [("user_type_1", None)], name="C")
    invited = await tenant.post(
        "/ui/v1/users", admin, {"login_identifier": f"{code}.new@zongovita.in", "display_name": "New"}
    )
    not_active = await tenant.post(
        "/ui/v1/super-admin/transfer", admin, {"user_id": invited.json()["user"]["id"]}
    )
    assert _problem(not_active) == (422, "VALIDATION_FAILED"), "the new super admin must be able to sign in"

    results = await asyncio.gather(
        tenant.post("/ui/v1/super-admin/transfer", admin, {"user_id": str(b.user_id), "reason": "handover"}),
        tenant.post("/ui/v1/super-admin/transfer", admin, {"user_id": str(c.user_id), "reason": "handover"}),
    )
    statuses = sorted(r.status_code for r in results)
    assert statuses == [200, 403], [r.text for r in results]
    winner = b if results[0].status_code == 200 else c
    holders = await _sql(
        stack,
        tenant.customer,
        "SELECT principal_id FROM iam.role_assignments WHERE super_admin AND revoked_at IS NULL",
    )
    assert [h for (h,) in holders] == [winner.user_id]

    old = (await tenant.get("/ui/v1/me", admin)).json()
    assert old["is_super_admin"] is False
    assert old["role_label"] == "User Type 1", "the former super admin keeps User Type 1"
    assert not RESERVED_TO_SUPER_ADMIN & set(_perms(old))
    new = (await tenant.get("/ui/v1/me", winner)).json()
    assert new["is_super_admin"] is True
    # The former super admin is now an ordinary user and can be deactivated.
    gone = await tenant.post(f"/ui/v1/users/{admin.user_id}/deactivate", winner, {"reason": "test"})
    assert gone.status_code == 200, gone.text


# ------------------------------------------------- privilege matrix, preview, cache invalidation
async def test_privilege_matrix_submit_writes_the_difference_and_takes_effect_at_once(
    tenant: Tenant, stack: Stack
) -> None:
    admin = tenant.super_admin
    assert admin is not None
    requester = await tenant.create_person(
        f"{tenant.customer.code}.req@zongovita.in", [("user_type_4", str(SITE_A))]
    )
    assert _problem(await tenant.get("/ui/v1/users", requester)) == (403, "PERMISSION_DENIED")

    matrix = await tenant.get("/ui/v1/privilege-matrix", admin)
    assert matrix.status_code == 200
    catalogue = {p["code"]: p for p in matrix.json()["permissions"]}
    assert set(catalogue) == ALL_CODES
    assert {c for c, p in catalogue.items() if p["reserved_to_super_admin"]} == RESERVED_TO_SUPER_ADMIN
    type4 = next(r for r in matrix.json()["roles"] if r["code"] == "user_type_4")
    assert set(type4["permissions"]) == SEEDED_BY_CODE["user_type_4"].permissions
    assert type4["assigned_principals"] == 1

    path = f"/ui/v1/roles/{type4['id']}/permissions"
    wanted = sorted(
        {*type4["permissions"], "access.user.manage", "inventory.stock.view"} - {"returns.return.create"}
    )
    submitted = await tenant.call(
        "PUT", path, admin, json={"permissions": wanted}, headers={"If-Match": f'"{type4["version"]}"'}
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["added"] == ["access.user.manage", "inventory.stock.view"]
    assert result["removed"] == ["returns.return.create"]
    (change,) = result["preview"]
    assert change["principal_id"] == str(requester.user_id)
    assert change["added"] == ["access.user.manage", "inventory.stock.view"]
    assert change["removed"] == ["returns.return.create"]
    effective = {p["code"]: p["site_ids"] for p in change["effective"]}
    assert effective["inventory.stock.view"] == [str(SITE_A)]
    assert effective["access.user.manage"] is None

    # The same token, no wait: the access version moved, so no cached permission is served.
    assert (await tenant.get("/ui/v1/users", requester)).status_code == 200
    stale = await tenant.call(
        "PUT", path, admin, json={"permissions": wanted}, headers={"If-Match": f'"{type4["version"]}"'}
    )
    assert _problem(stale) == (412, "VERSION_CONFLICT")

    audit = await _sql(
        stack,
        tenant.customer,
        "SELECT after->>'permission', after->>'granted' FROM audit.audit_log "
        "WHERE action = 'iam.role.permissions_changed' ORDER BY seq",
    )
    assert sorted(tuple(r) for r in audit) == [
        ("access.user.manage", "true"),
        ("inventory.stock.view", "true"),
        ("returns.return.create", "false"),
    ]


async def test_role_changes_need_a_reason_in_gxp_mode(
    stack: Stack, session_registry: RegistryService, core: CoreRuntime, clock: ManualClock, fresh_code: str
) -> None:
    async for gxp in _tenant(stack, session_registry, core, clock, fresh_code, gxp_mode=True):
        admin = gxp.super_admin
        assert admin is not None
        type4 = gxp.roles["user_type_4"]
        path = f"/ui/v1/roles/{type4['id']}/permissions"
        headers = {"If-Match": f'"{type4["version"]}"'}
        body = {"permissions": ["issuance.request.create"]}
        assert _problem(await gxp.call("PUT", path, admin, json=body, headers=headers)) == (
            422,
            "REASON_REQUIRED",
        )
        ok = await gxp.call(
            "PUT", path, admin, json={**body, "reason": "CAPA-12: returns by stores only"}, headers=headers
        )
        assert ok.status_code == 200, ok.text


# --------------------------------------------------------------------------- API clients
async def test_api_clients_hold_permissions_through_role_assignments(tenant: Tenant) -> None:
    admin = tenant.super_admin
    assert admin is not None
    reader = await tenant.post(
        "/ui/v1/roles", admin, {"name": "Stock reader", "permissions": ["inventory.stock.view"]}
    )
    created = await tenant.post(
        "/ui/v1/api-clients",
        admin,
        {"name": "ERP connector", "assignments": [{"role_id": reader.json()["id"], "site_id": None}]},
    )
    assert created.status_code == 201, created.text
    assert created.headers["cache-control"] == "no-store"
    client_id, secret = created.json()["client_id"], created.json()["client_secret"]
    never_super = await tenant.post(
        "/ui/v1/role-assignments",
        admin,
        {"principal_type": "api_client", "principal_id": client_id, "role_id": tenant.role_id("super_admin")},
    )
    assert _problem(never_super) == (403, "PERMISSION_DENIED")

    async def token(client_secret: str) -> httpx.Response:
        return await tenant.client.post(
            "/api/v1/oauth/token",
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        )

    issued = await token(secret)
    assert issued.status_code == 200, issued.text
    bearer = {"Authorization": f"Bearer {issued.json()['access_token']}"}
    assert (await tenant.client.get("/api/v1/test/stock-levels", headers=bearer)).status_code == 200
    denied = await tenant.client.post(
        "/api/v1/test/items", headers={**bearer, "Idempotency-Key": f"k-{uuid7()}"}
    )
    assert _problem(denied) == (403, "PERMISSION_DENIED")

    rotated = await tenant.post(f"/ui/v1/api-clients/{client_id}/rotate-secret", admin)
    assert rotated.status_code == 200
    assert _problem(await token(secret)) == (401, "AUTH_REQUIRED"), "the old secret stops working"
    assert (await token(rotated.json()["client_secret"])).status_code == 200

    disabled = await tenant.post(f"/ui/v1/api-clients/{client_id}/disable", admin)
    assert disabled.json()["status"] == "disabled"
    assert _problem(await tenant.client.get("/api/v1/test/stock-levels", headers=bearer)) == (
        401,
        "PRINCIPAL_INACTIVE",
    )
    listed = await tenant.get("/ui/v1/api-clients", admin)
    assert [c["status"] for c in listed.json()] == ["disabled"]


# --------------------------------------------------------------------------- rate limits
async def test_rate_limits_per_principal_and_per_customer(
    stack: Stack, session_registry: RegistryService, core: CoreRuntime, clock: ManualClock, fresh_code: str
) -> None:
    """LD-88: buckets per user and per customer; 429 RATE_LIMITED with Retry-After."""
    limits = RateLimits(user_per_minute=4, customer_per_minute=6)
    async for t in _tenant(stack, session_registry, core, clock, fresh_code, limits=limits):
        admin = t.super_admin
        assert admin is not None
        other = await t.create_person(f"{fresh_code}.other@zongovita.in", [("user_type_4", None)])
        clock.advance(seconds=60)  # every bucket full again after the setup requests

        for _ in range(4):
            assert (await t.get("/ui/v1/me", admin)).status_code == 200
        limited = await t.get("/ui/v1/me", admin)
        assert _problem(limited) == (429, "RATE_LIMITED")
        assert int(limited.headers["retry-after"]) >= 1

        # The other user has a bucket of their own, but the customer's has two tokens left.
        assert (await t.get("/ui/v1/me", other)).status_code == 200
        assert (await t.get("/ui/v1/me", other)).status_code == 200
        assert _problem(await t.get("/ui/v1/me", other)) == (429, "RATE_LIMITED")

        clock.advance(seconds=10)  # the customer bucket refills at 6 per minute: one token
        assert (await t.get("/ui/v1/me", other)).status_code == 200
        assert _problem(await t.get("/ui/v1/me", other)) == (429, "RATE_LIMITED")
