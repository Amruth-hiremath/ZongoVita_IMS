"""IMS Core for the browser tests that run against the real backend (Playwright project tenant-core).

    uv run python tools/e2e_backend.py

Starts from an empty test cluster (the ims-test stack; see README), exactly like the Python test
suite, so the two must not run at the same time. Then:

1. bootstraps the Control-Plane database and keys, and onboards customer "demo" through the real
   pipeline (database, roles, migrations, permission catalogue, seeded roles, licence);
2. creates the people the wireframes are drawn for, the way they will exist in production: the
   super admin as provisioning creates it, the others through POST /ui/v1/users with their
   seeded user types; each one activates, sets a password and enrols an authenticator;
3. writes their sign-in details to e2e/.auth/people.json (test data, git-ignored);
4. serves Core on 127.0.0.1:8180 with the Platform Service in the same process.

Nothing here is used outside tests: the stack refuses to wipe a cluster not marked as the test one.
"""

from __future__ import annotations

import asyncio
import base64
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ims_common.clock import SystemClock  # noqa: E402
from ims_common.pg import create_pooler_engine, use_selector_event_loop_on_windows  # noqa: E402
from ims_contracts.enums import LicenceModule  # noqa: E402
from ims_core.kernel.runtime import build_runtime  # noqa: E402
from ims_core.kernel.settings import CoreSettings  # noqa: E402
from ims_core.kernel.uow import unit_of_work  # noqa: E402
from ims_core.main import build_app  # noqa: E402
from ims_core.modules.identity import domain  # noqa: E402
from ims_platform.main import create_app as create_platform_app  # noqa: E402
from ims_platform.registry import RegistryService  # noqa: E402
from ims_platform.runtime import build_runtime as build_platform_runtime  # noqa: E402
from ims_platform.settings import PlatformSettings  # noqa: E402
from tests.support.stack import PG_HOST, POOLER_PORT, bootstrap, onboard_customer  # noqa: E402

PORT = 8180
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


def _code(secret: str) -> str:
    raw = base64.b32decode(secret + "=" * (-len(secret) % 8))
    return domain.totp_code(raw, domain.totp_step(datetime.now(UTC)))


async def _activate_and_enrol(
    client: httpx.AsyncClient, identifier: str, activation_code: str
) -> dict[str, Any]:
    async def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = await client.post(f"/ui/v1/auth/{path}", json=body)
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


async def main() -> None:
    use_selector_event_loop_on_windows()
    shutil.rmtree(STATE, ignore_errors=True)
    stack = await bootstrap(STATE)
    clock = SystemClock()

    platform_settings = PlatformSettings(
        environment="test",
        db_pooler_host=PG_HOST,
        db_pooler_port=POOLER_PORT,
        db_sslmode="disable",
        secrets_root=stack.secrets_root,
        object_store_root=stack.objects_root,
    )
    platform = await build_platform_runtime(
        platform_settings, secrets=stack.platform_secrets, object_store=stack.object_store, clock=clock
    )
    platform_app = create_platform_app(runtime=platform, run_bundle_publisher=False)

    credential = await stack.platform_secrets.get("platform/db-app")
    setup_engine = create_pooler_engine(
        host=PG_HOST,
        port=POOLER_PORT,
        database="ims_control_plane",
        user="platform_app",
        password=credential["password"],
        application_name="ims-e2e-setup",
        pool_size=2,
        max_overflow=0,
        pool_timeout_s=10,
        sslmode="disable",
    )
    customer = await onboard_customer(stack, RegistryService(setup_engine), "demo", now=datetime.now(UTC))
    await setup_engine.dispose()

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

    people: dict[str, dict[str, Any]] = {}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://core") as client:
        ctx = await core.credential_context(
            customer.id, module=LicenceModule.CORE, request_id="e2e-provisioning", source="system"
        )
        async with unit_of_work(core.router, ctx, clock) as uow:
            created = await app.state.access.bootstrap_super_admin(
                uow, login_identifier=SUPER_ADMIN[0], display_name=SUPER_ADMIN[1], email=SUPER_ADMIN[0]
            )
        admin = await _activate_and_enrol(client, SUPER_ADMIN[0], created.activation_code)
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
    for person in people.values():
        person.pop("token")
    PEOPLE_FILE.write_text(
        json.dumps({"customer": customer.code, "people": people}, indent=2), encoding="utf-8"
    )

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning", lifespan="on")
    )
    print(f"IMS Core for e2e on http://127.0.0.1:{PORT} (customer {customer.code})", flush=True)  # noqa: T201
    try:
        await server.serve()
    finally:
        await core.aclose()
        await platform.aclose()


if __name__ == "__main__":
    use_selector_event_loop_on_windows()
    asyncio.run(main())
