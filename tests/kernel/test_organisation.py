"""Organisation and licence limits through the real pipeline (LLD 5.1, 12; AD-27, #30).

Real tokens from real sign-ins, the licence gate, the customer database through the pooler, the
principal, rate-limit and authorise stages, idempotency and audit.
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
from ims_platform.registry import RegistryService
from tests.support.stack import Customer, Stack, onboard_customer
from tests.support.tenant import Person, Tenant, full_app

pytestmark = pytest.mark.db


async def _tenant(
    stack: Stack,
    registry: RegistryService,
    core: CoreRuntime,
    clock: ManualClock,
    code: str,
    **onboarding: Any,
) -> AsyncIterator[Tenant]:
    customer = await onboard_customer(stack, registry, code, now=clock.now(), **onboarding)
    app = full_app(core)
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


def _site_body(code: str, *, status: str = "staged", timezone: str = "Asia/Kolkata") -> dict[str, Any]:
    return {
        "code": code,
        "name": f"Site {code}",
        "timezone": timezone,
        "status": status,
        "default_location": {"code": f"{code}-MAIN", "name": f"{code} main store"},
    }


async def _sql(stack: Stack, customer: Customer, sql: str, **params: Any) -> list[Any]:
    engine = await stack.migration_engine(customer.db)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(sql), params)
            return list(result.all()) if result.returns_rows else []
    finally:
        await engine.dispose()


def _admin(tenant: Tenant) -> Person:
    assert tenant.super_admin is not None
    return tenant.super_admin


# ------------------------------------------------------------------------------------- sites
async def test_sites_are_created_with_their_default_location_and_edited_with_if_match(
    tenant: Tenant, stack: Stack
) -> None:
    admin = _admin(tenant)
    created = await tenant.post("/ui/v1/sites", admin, _site_body("WH-BLR-01", status="active"))
    assert created.status_code == 201, created.text
    site, default = created.json()["site"], created.json()["default_location"]
    assert (site["status"], site["timezone"]) == ("active", "Asia/Kolkata")
    assert (default["is_default"], default["status"], default["site_id"]) == (True, "active", site["id"])

    # Codes are unique whatever their case; timezones are IANA names.
    duplicate = await tenant.post("/ui/v1/sites", admin, _site_body("wh-blr-01"))
    assert _problem(duplicate) == (422, "VALIDATION_FAILED")
    assert duplicate.json()["errors"][0]["field"] == "code"
    bad_zone = await tenant.post("/ui/v1/sites", admin, _site_body("WH-X", timezone="India/Bengaluru"))
    assert bad_zone.json()["errors"][0]["field"] == "timezone"

    read = await tenant.get(f"/ui/v1/sites/{site['id']}", admin)
    edit = {"name": "Bengaluru Central Warehouse", "timezone": "Europe/Berlin"}
    path = f"/ui/v1/sites/{site['id']}"
    assert _problem(await tenant.call("PATCH", path, admin, json=edit)) == (428, "PRECONDITION_REQUIRED")
    assert _problem(await tenant.call("PATCH", path, admin, json=edit, headers={"If-Match": '"9"'})) == (
        412,
        "VERSION_CONFLICT",
    )
    done = await tenant.call("PATCH", path, admin, json=edit, headers={"If-Match": read.headers["etag"]})
    assert done.status_code == 200, done.text
    assert done.json()["name"] == "Bengaluru Central Warehouse"
    assert done.json()["code"] == "WH-BLR-01", "codes are fixed once created"

    listed = await tenant.get("/ui/v1/sites", admin, params={"status": "active"})
    assert [s["code"] for s in listed.json()["items"]] == ["WH-BLR-01"]
    audit = await _sql(
        stack, tenant.customer, "SELECT action FROM audit.audit_log WHERE entity_type LIKE 'org.%'"
    )
    assert sorted(a for (a,) in audit) == ["org.location.created", "org.site.created", "org.site.updated"]


async def test_site_transitions(tenant: Tenant) -> None:
    admin = _admin(tenant)
    site = (await tenant.post("/ui/v1/sites", admin, _site_body("PUN-02"))).json()["site"]
    url = f"/ui/v1/sites/{site['id']}"
    assert (await tenant.post(f"{url}/activate", admin)).json()["status"] == "active"
    assert _problem(await tenant.post(f"{url}/activate", admin)) == (409, "INVALID_STATE_TRANSITION")
    assert (await tenant.post(f"{url}/deactivate", admin)).json()["status"] == "inactive"
    assert _problem(await tenant.post(f"{url}/deactivate", admin)) == (409, "INVALID_STATE_TRANSITION")
    assert (await tenant.post(f"{url}/activate", admin)).json()["status"] == "active"


async def test_the_licence_site_limit_holds_at_creation_and_reactivation(tenant: Tenant) -> None:
    """AD-27 and #30: staged and active sites count; creation and re-activation are refused at
    the limit (the test licence allows 5 sites); concurrent creations cannot overshoot."""
    admin = _admin(tenant)
    ids = []
    for n in range(3):
        response = await tenant.post(
            "/ui/v1/sites", admin, _site_body(f"S{n}", status="active" if n else "staged")
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["site"]["id"])
    # Two at once for the last two places, then a third concurrent one: exactly two succeed.
    racing = await asyncio.gather(
        *(tenant.post("/ui/v1/sites", admin, _site_body(f"R{n}")) for n in range(3))
    )
    assert sorted(r.status_code for r in racing) == [201, 201, 409]
    assert {r.json()["code"] for r in racing if r.status_code == 409} == {"LIMIT_EXCEEDED"}

    # An inactive site does not count: deactivate one, and another can be created.
    assert (await tenant.post(f"/ui/v1/sites/{ids[0]}/deactivate", admin)).status_code == 200
    assert (await tenant.post("/ui/v1/sites", admin, _site_body("S9"))).status_code == 201
    # Re-activating the inactive one would exceed the limit again.
    assert _problem(await tenant.post(f"/ui/v1/sites/{ids[0]}/activate", admin)) == (409, "LIMIT_EXCEEDED")
    # Staged to active changes nothing in the count.
    staged = [
        s for s in (await tenant.get("/ui/v1/sites", admin, params={"status": "staged"})).json()["items"]
    ]
    assert (await tenant.post(f"/ui/v1/sites/{staged[0]['id']}/activate", admin)).status_code == 200


# --------------------------------------------------------------------------------- locations
async def test_locations_and_the_default(tenant: Tenant) -> None:
    admin = _admin(tenant)
    created = (await tenant.post("/ui/v1/sites", admin, _site_body("HYD-03", status="active"))).json()
    site_id, main = created["site"]["id"], created["default_location"]
    second = await tenant.post(
        "/ui/v1/locations", admin, {"site_id": site_id, "code": "HYD-03-QC", "name": "Quality store"}
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]
    assert second.json()["is_default"] is False
    duplicate = await tenant.post(
        "/ui/v1/locations", admin, {"site_id": site_id, "code": "hyd-03-main", "name": "X"}
    )
    assert _problem(duplicate) == (422, "VALIDATION_FAILED")
    unknown = await tenant.post(
        "/ui/v1/locations",
        admin,
        {"site_id": "018f6f2a-0000-7000-8000-0000000000ff", "code": "NOPE", "name": "X"},
    )
    assert unknown.json()["errors"][0]["field"] == "site_id"

    # The default cannot be deactivated; moving the default is one command.
    assert _problem(await tenant.post(f"/ui/v1/locations/{main['id']}/deactivate", admin)) == (
        409,
        "INVALID_STATE_TRANSITION",
    )
    moved = await tenant.post(f"/ui/v1/locations/{second_id}/make-default", admin)
    assert moved.json()["is_default"] is True
    listed = await tenant.get("/ui/v1/locations", admin, params={"site_id": site_id})
    assert {loc["code"]: loc["is_default"] for loc in listed.json()["items"]} == {
        "HYD-03-MAIN": False,
        "HYD-03-QC": True,
    }
    assert (await tenant.post(f"/ui/v1/locations/{main['id']}/deactivate", admin)).json()[
        "status"
    ] == "inactive"
    assert _problem(await tenant.post(f"/ui/v1/locations/{main['id']}/make-default", admin)) == (
        409,
        "INVALID_STATE_TRANSITION",
    )
    read = await tenant.get(f"/ui/v1/locations/{second_id}", admin)
    renamed = await tenant.call(
        "PATCH",
        f"/ui/v1/locations/{second_id}",
        admin,
        json={"name": "Quality hold store"},
        headers={"If-Match": read.headers["etag"]},
    )
    assert renamed.json()["name"] == "Quality hold store"


# ------------------------------------------------------------------------------- departments
async def test_departments(tenant: Tenant) -> None:
    admin = _admin(tenant)
    created = await tenant.post("/ui/v1/departments", admin, {"code": "MNT", "name": "Maintenance"})
    assert created.status_code == 201, created.text
    department = created.json()
    assert _problem(await tenant.post("/ui/v1/departments", admin, {"code": "mnt", "name": "Again"})) == (
        422,
        "VALIDATION_FAILED",
    )
    url = f"/ui/v1/departments/{department['id']}"
    read = await tenant.get(url, admin)
    renamed = await tenant.call(
        "PATCH", url, admin, json={"name": "Plant maintenance"}, headers={"If-Match": read.headers["etag"]}
    )
    assert renamed.json()["name"] == "Plant maintenance"
    assert (await tenant.post(f"{url}/deactivate", admin)).json()["status"] == "inactive"
    listed = await tenant.get("/ui/v1/departments", admin, params={"status": "active"})
    assert listed.json()["items"] == []


# --------------------------------------------------------------------- permissions and scope
async def test_reference_data_is_for_everyone_and_changes_need_the_org_permissions(tenant: Tenant) -> None:
    admin = _admin(tenant)
    site = (await tenant.post("/ui/v1/sites", admin, _site_body("BLR", status="active"))).json()["site"]
    requester = await tenant.create_person(
        f"{tenant.customer.code}.req@zongovita.in", [("user_type_4", site["id"])]
    )
    for path in ("/ui/v1/sites", "/ui/v1/locations", "/ui/v1/departments"):
        assert (await tenant.get(path, requester)).status_code == 200, path
    for path, body in (
        ("/ui/v1/sites", _site_body("NOPE")),
        ("/ui/v1/locations", {"site_id": site["id"], "code": "NOPE", "name": "X"}),
        ("/ui/v1/departments", {"code": "NOPE", "name": "X"}),
        (f"/ui/v1/sites/{site['id']}/deactivate", {}),
    ):
        assert _problem(await tenant.post(path, requester, body)) == (403, "PERMISSION_DENIED"), path


async def test_users_and_assignments_refer_to_real_sites_and_departments(tenant: Tenant) -> None:
    admin = _admin(tenant)
    code = tenant.customer.code
    blr = (await tenant.post("/ui/v1/sites", admin, _site_body("BLR", status="active"))).json()["site"]
    pun = (await tenant.post("/ui/v1/sites", admin, _site_body("PUN", status="active"))).json()["site"]
    staged = (await tenant.post("/ui/v1/sites", admin, _site_body("MAA"))).json()["site"]
    department = (await tenant.post("/ui/v1/departments", admin, {"code": "STORES", "name": "Stores"})).json()
    old = (await tenant.post("/ui/v1/departments", admin, {"code": "OLD", "name": "Old"})).json()
    await tenant.post(f"/ui/v1/departments/{old['id']}/deactivate", admin)

    def user(name: str, **extra: Any) -> dict[str, Any]:
        return {"login_identifier": f"{code}.{name}@zongovita.in", "display_name": name, **extra}

    no_site = await tenant.post(
        "/ui/v1/users",
        admin,
        user(
            "x",
            assignments=[
                {"role_id": tenant.role_id("user_type_3"), "site_id": "018f6f2a-0000-7000-8000-0000000000ff"}
            ],
        ),
    )
    assert no_site.json()["errors"][0]["field"] == "assignments[0].site_id"
    inactive_department = await tenant.post("/ui/v1/users", admin, user("y", department_id=old["id"]))
    assert inactive_department.json()["errors"][0]["field"] == "department_id"

    # A store user at one site: /me lists that site and the home site.
    store = await tenant.create_person(f"{code}.store@zongovita.in", [("user_type_3", blr["id"])])
    store_user = (await tenant.get(f"/ui/v1/users/{store.user_id}", admin)).json()
    edit = {
        "display_name": "Suresh Patil",
        "email": None,
        "department_id": department["id"],
        "home_site_id": blr["id"],
    }
    etag = (await tenant.get(f"/ui/v1/users/{store.user_id}", admin)).headers["etag"]
    edited = await tenant.call(
        "PATCH", f"/ui/v1/users/{store.user_id}", admin, json=edit, headers={"If-Match": etag}
    )
    assert edited.status_code == 200, edited.text
    assert (edited.json()["department_id"], edited.json()["home_site_id"]) == (department["id"], blr["id"])
    assert store_user["home_site_id"] is None
    me = (await tenant.get("/ui/v1/me", store)).json()
    assert [s["code"] for s in me["sites"]] == ["BLR"]
    assert me["home_site_id"] == blr["id"]

    # Every site: every active site (staged ones hold no stock and are not offered).
    manager = await tenant.create_person(f"{code}.manager@zongovita.in", [("user_type_2", None)])
    assert [s["code"] for s in (await tenant.get("/ui/v1/me", manager)).json()["sites"]] == ["BLR", "PUN"]
    assert [s["code"] for s in (await tenant.get("/ui/v1/me", admin)).json()["sites"]] == ["BLR", "PUN"]
    # A deactivated site leaves /me.
    await tenant.post(f"/ui/v1/sites/{pun['id']}/deactivate", admin)
    assert [s["code"] for s in (await tenant.get("/ui/v1/me", manager)).json()["sites"]] == ["BLR"]
    assert staged["status"] == "staged"


async def test_public_api_reference_data(tenant: Tenant) -> None:
    admin = _admin(tenant)
    await tenant.post("/ui/v1/sites", admin, _site_body("BLR", status="active"))
    created = await tenant.post("/ui/v1/api-clients", admin, {"name": "ERP"})
    client_id, secret = created.json()["client_id"], created.json()["client_secret"]
    token = await tenant.client.post(
        "/api/v1/oauth/token",
        data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret},
    )
    bearer = {"Authorization": f"Bearer {token.json()['access_token']}"}
    sites = await tenant.client.get("/api/v1/sites", headers=bearer)
    assert sites.status_code == 200, sites.text
    assert [s["code"] for s in sites.json()["items"]] == ["BLR"]
    locations = await tenant.client.get("/api/v1/locations", headers=bearer)
    assert [loc["code"] for loc in locations.json()["items"]] == ["BLR-MAIN"]


async def test_read_only_licence_serves_reference_data_and_refuses_changes(
    stack: Stack, session_registry: RegistryService, core: CoreRuntime, clock: ManualClock, fresh_code: str
) -> None:
    """LD-77: in read-only state GET routes still work; every organisation write is refused."""
    async for t in _tenant(stack, session_registry, core, clock, fresh_code, valid_for_days=1, grace_days=0):
        clock.set(t.customer.valid_until + timedelta(minutes=1))  # past the end date, no grace
        admin = await t.sign_in_again(_admin(t))  # the earlier session has expired meanwhile
        assert (await t.get("/ui/v1/sites", admin)).status_code == 200
        me = (await t.get("/ui/v1/me", admin)).json()
        assert me["licence"]["state"] == "read_only"
        assert _problem(await t.post("/ui/v1/sites", admin, _site_body("RO"))) == (403, "LICENCE_READ_ONLY")
        assert _problem(await t.post("/ui/v1/departments", admin, {"code": "RO", "name": "X"})) == (
            403,
            "LICENCE_READ_ONLY",
        )
