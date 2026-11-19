"""IMS Core and the Platform Service for the browser tests that run against the real backend
(Playwright projects tenant-core and console-platform).

    uv run python tools/e2e_backend.py

Starts from an empty test cluster (the ims-test stack; see README), exactly like the Python test
suite, so the two must not run at the same time. Then:

1. bootstraps the Control-Plane database and keys;
2. creates the ZongoVita staff the Platform Console is used by (a system admin and a support
   engineer, HLD section 3), each activated with a password and an enrolled authenticator;
3. onboards customer "demo" the way production does: the system admin starts a provisioning run
   through POST /platform/v1/provisioning-runs, the run creates and migrates the database through
   the database pipeline (in-process here), IMS Core creates the super admin, and the activation
   code is handed over once (LLD 6.6, AD-28);
4. creates the people the wireframes are drawn for: the super admin activates with the handed-over
   code, the others are created through POST /ui/v1/users with their seeded user types; each one
   sets a password and enrols an authenticator;
5. writes everyone's sign-in details to e2e/.auth/people.json (test data, git-ignored);
6. serves Core on 127.0.0.1:8180 and the Platform Service on 127.0.0.1:8181.

Nothing here is used outside tests: the stack refuses to wipe a cluster not marked as the test one.
"""

from __future__ import annotations

import asyncio
import base64
import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ims_common import auth_codes as domain  # noqa: E402
from ims_common.clock import SystemClock  # noqa: E402
from ims_common.pg import use_selector_event_loop_on_windows  # noqa: E402
from ims_contracts.enums import LicenceModule  # noqa: E402
from ims_core.kernel.runtime import build_runtime  # noqa: E402
from ims_core.kernel.settings import CoreSettings  # noqa: E402
from ims_core.main import build_app  # noqa: E402
from ims_platform.accounts import StaffRole  # noqa: E402
from ims_platform.main import create_app as create_platform_app  # noqa: E402
from ims_platform.registry import Actor  # noqa: E402
from ims_platform.runtime import PlatformRuntime  # noqa: E402
from ims_platform.runtime import build_runtime as build_platform_runtime  # noqa: E402
from ims_platform.settings import PlatformSettings  # noqa: E402
from tests.support.platform import InProcessPipeline  # noqa: E402
from tests.support.stack import PG_HOST, POOLER_PORT, bootstrap  # noqa: E402

PORT = 8180
PLATFORM_PORT = 8181
STATE = ROOT / ".local" / "e2e"
PEOPLE_FILE = ROOT / "e2e" / ".auth" / "people.json"
PASSWORD = "e2e correct horse battery"  # noqa: S105 - test value, written to the git-ignored people file
#: The demo customer's sites (codes and names as F21 draws them), created through POST /ui/v1/sites.
SITES: list[tuple[str, str, str]] = [
    ("WH-BLR-01", "Bengaluru Central Warehouse", "active"),
    ("WH-PUN-02", "Pune Plant Store", "staged"),
    ("ST-MAA-01", "Chennai Retail Store", "staged"),
    ("WH-HYD-03", "Hyderabad Depot", "staged"),
]
DEPARTMENTS: list[tuple[str, str]] = [("STORES", "Stores"), ("MAINT", "Maintenance")]

#: persona -> (identifier, display name, seeded role assignments by site code, home site, department)
PEOPLE: dict[str, tuple[str, str, list[tuple[str, str | None]], str | None, str | None]] = {
    "type2": ("priya.sharma@demo.test", "Priya Sharma", [("user_type_2", None)], "WH-BLR-01", None),
    "type3": (
        "suresh.patil@demo.test",
        "Suresh Patil",
        [("user_type_3", "WH-BLR-01")],
        "WH-BLR-01",
        "STORES",
    ),
    "type4": ("meera.joshi@demo.test", "Meera Joshi", [("user_type_4", "WH-BLR-01")], "WH-BLR-01", "MAINT"),
}
SUPER_ADMIN = ("arjun.mehta@demo.test", "Arjun Mehta")
CUSTOMER = ("demo", "Demo Manufacturing Pvt Ltd")
#: ZongoVita staff (HLD section 3 actors): role -> (identifier, display name).
STAFF: dict[StaffRole, tuple[str, str]] = {
    StaffRole.SYSTEM_ADMIN: ("kiran.desai@zongovita.test", "Kiran Desai"),
    StaffRole.SUPPORT_ENGINEER: ("rohan.kulkarni@zongovita.test", "Rohan Kulkarni"),
}


def _code(secret: str) -> str:
    raw = base64.b32decode(secret + "=" * (-len(secret) % 8))
    return domain.totp_code(raw, domain.totp_step(datetime.now(UTC)))


async def _activate_and_enrol(
    client: httpx.AsyncClient, identifier: str, activation_code: str, *, api: str = "/ui/v1"
) -> dict[str, Any]:
    """Activation, first sign-in, authenticator enrolment and the first code, through the API."""

    async def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = await client.post(f"{api}/auth/{path}", json=body)
        if response.status_code >= 300:
            raise RuntimeError(f"{path} for {identifier}: {response.status_code} {response.text}")
        return response.json() if response.content else {}

    await post(
        "activate",
        {"login_identifier": identifier, "activation_code": activation_code, "new_password": PASSWORD},
    )
    challenge = (await post("login", {"login_identifier": identifier, "password": PASSWORD}))[
        "challenge_token"
    ]
    secret = (await post("mfa/enrol", {"challenge_token": challenge}))["secret"]
    step = domain.totp_step(datetime.now(UTC))
    session = await post("mfa", {"challenge_token": challenge, "code": _code(secret)})
    return {
        "identifier": identifier,
        "password": PASSWORD,
        "secret": secret,
        "last_step": step,
        "token": session["access_token"],
    }


async def _onboard_demo(
    client: httpx.AsyncClient, admin_token: str, platform: PlatformRuntime
) -> dict[str, Any]:
    """Customer "demo" through the real provisioning run, as a system admin starts it (LLD 6.6)."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    now = datetime.now(UTC)
    started = await client.post(
        "/platform/v1/provisioning-runs",
        headers=headers,
        json={
            "customer": {"code": CUSTOMER[0], "legal_name": CUSTOMER[1]},
            "licence": {
                "licence_no": f"LIC-{CUSTOMER[0].upper()}-1",
                "valid_from": (now - timedelta(days=1)).isoformat(),
                "valid_until": (now + timedelta(days=365)).isoformat(),
                "grace_days": 14,
                "max_sites": 5,
                "max_users": 200,
                "modules": sorted(m.value for m in LicenceModule),
            },
            "super_admin": {
                "login_identifier": SUPER_ADMIN[0],
                "display_name": SUPER_ADMIN[1],
                "email": SUPER_ADMIN[0],
            },
        },
    )
    if started.status_code != 202:
        raise RuntimeError(f"starting provisioning: {started.status_code} {started.text}")
    run_id = started.json()["id"]
    await platform.provisioning.wait_for_background()
    run = (await client.get(f"/platform/v1/provisioning-runs/{run_id}", headers=headers)).json()
    if run["status"] != "completed":
        raise RuntimeError(f"provisioning did not complete: {run}")
    handover = await client.post(f"/platform/v1/provisioning-runs/{run_id}/handover", headers=headers)
    if handover.status_code != 200:
        raise RuntimeError(f"handover: {handover.status_code} {handover.text}")
    return {"run": run, "activation_code": handover.json()["activation_code"]}


async def main() -> None:
    use_selector_event_loop_on_windows()
    shutil.rmtree(STATE, ignore_errors=True)
    stack = await bootstrap(STATE)
    clock = SystemClock()

    # The Platform Service calls IMS Core (provisioning step 6) and Core calls the Platform Service
    # (registry, directory). Core's app exists only after the platform's, so the platform reaches
    # it through this late-bound entry point.
    apps: dict[str, Any] = {}

    async def core_asgi(scope: Any, receive: Any, send: Any) -> None:
        await apps["core"](scope, receive, send)

    platform_settings = PlatformSettings(
        environment="test",
        db_pooler_host=PG_HOST,
        db_pooler_port=POOLER_PORT,
        db_sslmode="disable",
        secrets_root=stack.secrets_root,
        object_store_root=stack.objects_root,
        core_base_url="http://core",
    )
    platform = await build_platform_runtime(
        platform_settings,
        secrets=stack.platform_secrets,
        object_store=stack.object_store,
        clock=clock,
        pipeline=InProcessPipeline(stack),
        core_transport=httpx.ASGITransport(app=core_asgi),
    )
    platform_app = create_platform_app(runtime=platform, run_bundle_publisher=False)

    core_settings = CoreSettings(
        environment="test",
        instance="e2e-core",
        platform_base_url="http://platform.internal",
        db_sslmode="disable",
        secrets_root=stack.secrets_root,
        object_store_root=stack.objects_root,
    )
    core = await build_runtime(
        core_settings,
        secrets=stack.core_secrets,
        object_store=stack.object_store,
        clock=clock,
        registry_transport=httpx.ASGITransport(app=platform_app),
    )
    app = build_app(runtime=core, run_change_feed=True)
    apps["core"] = app

    staff: dict[str, dict[str, Any]] = {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=platform_app), base_url="http://platform"
    ) as console:
        for role, (identifier, name) in STAFF.items():
            invited = await platform.accounts.create_user(
                Actor("system:e2e-setup"),
                login_identifier=identifier,
                display_name=name,
                email=identifier,
                role=role,
            )
            staff[role.value] = await _activate_and_enrol(
                console, identifier, invited.activation_code, api="/platform/v1"
            )
        onboarding = await _onboard_demo(console, staff[StaffRole.SYSTEM_ADMIN.value]["token"], platform)

    people: dict[str, dict[str, Any]] = {}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://core") as client:
        admin = await _activate_and_enrol(client, SUPER_ADMIN[0], onboarding["activation_code"])
        people["type1"] = admin
        headers = {"Authorization": f"Bearer {admin['token']}"}
        roles = {r["code"]: r["id"] for r in (await client.get("/ui/v1/roles", headers=headers)).json()}
        sites: dict[str, str] = {}
        for code, name, status in SITES:
            created_site = await client.post(
                "/ui/v1/sites",
                headers={**headers, "Idempotency-Key": f"e2e-site-{code}"},
                json={
                    "code": code,
                    "name": name,
                    "timezone": "Asia/Kolkata",
                    "status": status,
                    "default_location": {"code": f"{code}-MAIN", "name": f"{name} — main store"},
                },
            )
            if created_site.status_code != 201:
                raise RuntimeError(f"creating site {code}: {created_site.status_code} {created_site.text}")
            sites[code] = created_site.json()["site"]["id"]
        departments: dict[str, str] = {}
        for code, name in DEPARTMENTS:
            created_department = await client.post(
                "/ui/v1/departments",
                headers={**headers, "Idempotency-Key": f"e2e-department-{code}"},
                json={"code": code, "name": name},
            )
            departments[code] = created_department.json()["id"]
        for persona, (identifier, name, assignments, home, department) in PEOPLE.items():
            response = await client.post(
                "/ui/v1/users",
                headers={**headers, "Idempotency-Key": f"e2e-{persona}"},
                json={
                    "login_identifier": identifier,
                    "display_name": name,
                    "email": identifier,
                    "home_site_id": sites[home] if home else None,
                    "department_id": departments[department] if department else None,
                    "assignments": [
                        {"role_id": roles[code], "site_id": sites[site] if site else None}
                        for code, site in assignments
                    ],
                },
            )
            if response.status_code != 201:
                raise RuntimeError(f"creating {persona}: {response.status_code} {response.text}")
            people[persona] = await _activate_and_enrol(
                client, identifier, response.json()["activation_code"]
            )

    PEOPLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    for person in [*people.values(), *staff.values()]:
        person.pop("token")
    PEOPLE_FILE.write_text(
        json.dumps(
            {
                "customer": CUSTOMER[0],
                "people": people,
                "staff": staff,
                "provisioning_run": onboarding["run"]["id"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    servers = [
        uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning", lifespan="on")),
        uvicorn.Server(
            uvicorn.Config(
                platform_app, host="127.0.0.1", port=PLATFORM_PORT, log_level="warning", lifespan="on"
            )
        ),
    ]
    print(  # noqa: T201
        f"IMS Core on http://127.0.0.1:{PORT}, Platform Service on http://127.0.0.1:{PLATFORM_PORT} "
        f"(customer {CUSTOMER[0]})",
        flush=True,
    )
    try:
        await asyncio.gather(*(server.serve() for server in servers))
    finally:
        await core.aclose()
        await platform.aclose()


if __name__ == "__main__":
    use_selector_event_loop_on_windows()
    asyncio.run(main())
