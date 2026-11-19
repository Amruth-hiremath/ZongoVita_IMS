"""Provisioning runs (LLD 6.6, 4; AD-28, AD-13, LD-85): onboarding a customer through the Platform
Service with the real database pipeline, the real Registry and the real IMS Core.

A run is a resumable step sequence: a failed step stops the run, keeps the error, and a resume
continues from that step without repeating finished ones or touching other customers. Every
step is safe to repeat, including the one whose effect committed but whose answer was lost.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text

from ims_common.clock import ManualClock
from ims_common.secrets import SecretAccessDeniedError, db_secret_ref
from ims_common.service_auth import ServiceTokenIssuer
from ims_contracts.enums import Placement
from ims_core.kernel.runtime import CoreRuntime
from ims_core.schema.version import SCHEMA_HEAD
from ims_db_pipeline.provision import CustomerDatabase
from ims_platform.registry import RegistryService
from tests.support.platform import Console, Staff, console_for
from tests.support.stack import Customer, Stack
from tests.support.tenant import PASSWORD as USER_PASSWORD
from tests.support.tenant import full_app

pytestmark = pytest.mark.db


@pytest_asyncio.fixture
async def core_asgi(core: CoreRuntime) -> FastAPI:
    """The full Core application (not the probe app of tests/conftest.py)."""
    return full_app(core)


@pytest_asyncio.fixture
async def console(
    stack: Stack, clock: ManualClock, core: CoreRuntime, core_asgi: FastAPI
) -> AsyncIterator[Console]:
    async with console_for(stack, clock, core, core_asgi) as c:
        yield c


@pytest_asyncio.fixture
async def admin(console: Console, fresh_code: str) -> Staff:
    return await console.staff(f"{fresh_code}.kiran@zongovita.test")


def _problem(response: httpx.Response) -> tuple[int, str]:
    return response.status_code, response.json()["code"]


def _request(code: str, now: Any, **customer: Any) -> dict[str, Any]:
    return {
        "customer": {"code": code, "legal_name": f"Acme {code} Pvt Ltd", **customer},
        "licence": {
            "licence_no": f"LIC-{code}-1",
            "valid_from": (now - timedelta(days=1)).isoformat(),
            "valid_until": (now + timedelta(days=365)).isoformat(),
            "max_sites": 5,
            "max_users": 50,
            "modules": ["ims.core", "ims.integration"],
        },
        "super_admin": {
            "login_identifier": f"{code}.owner@acme.test",
            "display_name": "Anita Rao",
            "email": None,
        },
    }


async def _start(console: Console, admin: Staff, code: str, **customer: Any) -> dict[str, Any]:
    started = await console.call(
        "POST", "/provisioning-runs", admin, json=_request(code, console.clock.now(), **customer)
    )
    assert started.status_code == 202, started.text
    await console.settle()
    return (await console.call("GET", f"/provisioning-runs/{started.json()['id']}", admin)).json()


async def _customer_rows(stack: Stack, code: str, sql: str) -> list[Any]:
    target = CustomerDatabase.for_customer(code)
    engine = await stack.migration_engine(target)
    try:
        async with engine.connect() as conn:
            return list((await conn.execute(text(sql))).all())
    finally:
        await engine.dispose()


async def _activate_and_sign_in(core_asgi: FastAPI, identifier: str, activation_code: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=core_asgi), base_url="http://core"
    ) as client:
        activated = await client.post(
            "/ui/v1/auth/activate",
            json={
                "login_identifier": identifier,
                "activation_code": activation_code,
                "new_password": USER_PASSWORD,
            },
        )
        if activated.status_code != 204:
            return activated
        return await client.post(
            "/ui/v1/auth/login", json={"login_identifier": identifier, "password": USER_PASSWORD}
        )


# ------------------------------------------------------------------------------ end to end
async def test_a_customer_is_onboarded_end_to_end(
    console: Console,
    admin: Staff,
    stack: Stack,
    session_registry: RegistryService,
    core_asgi: FastAPI,
    fresh_code: str,
) -> None:
    run = await _start(console, admin, fresh_code)
    assert (run["status"], run["current_step"], run["attempts"]) == ("completed", "done", 0), run
    assert set(run["results"]) == {
        "register",
        "database",
        "register_database",
        "migrate",
        "initial_users",
        "activate",
    }
    assert run["results"]["migrate"]["schema_version"] == SCHEMA_HEAD
    assert run["handover_available"] is True

    customer = (await console.call("GET", f"/customers/{run['customer_id']}", admin)).json()
    assert (customer["status"], customer["licence_state"]) == ("active", "active")
    assert customer["database"] == {
        "database_name": f"ims_c_{fresh_code}",
        "cluster_ref": stack.cluster.cluster_ref,
        "status": "ready",
        "schema_version": SCHEMA_HEAD,
    }
    assert await session_registry.get_snapshot(UUID(run["customer_id"])) is not None

    # The pipeline created the customer's credentials; the Platform Service cannot read them (AD-13).
    for kind in ("app", "migration", "breakglass"):
        assert await stack.pipeline_secrets.get(db_secret_ref(fresh_code, kind))
        with pytest.raises(SecretAccessDeniedError):
            await stack.platform_secrets.get(db_secret_ref(fresh_code, kind))

    # The customer's own database: seeded roles and the super admin, created by Core (AD-13).
    roles = await _customer_rows(stack, fresh_code, "SELECT code FROM iam.roles ORDER BY code")
    assert [r for (r,) in roles] == [
        "super_admin",
        "user_type_1",
        "user_type_2",
        "user_type_3",
        "user_type_4",
    ]
    holders = await _customer_rows(
        stack,
        fresh_code,
        "SELECT u.login_identifier, u.status, r.code FROM iam.role_assignments a JOIN iam.users u ON u.id = a.principal_id "
        "JOIN iam.roles r ON r.id = a.role_id WHERE a.revoked_at IS NULL ORDER BY r.code",
    )
    assert [tuple(h) for h in holders] == [
        (f"{fresh_code}.owner@acme.test", "invited", "super_admin"),
        (f"{fresh_code}.owner@acme.test", "invited", "user_type_1"),
    ]

    # The activation code is shown once, to hand over (#21), and it works.
    handover = await console.call("POST", f"/provisioning-runs/{run['id']}/handover", admin)
    assert handover.status_code == 200, handover.text
    assert handover.headers["cache-control"] == "no-store"
    assert _problem(await console.call("POST", f"/provisioning-runs/{run['id']}/handover", admin)) == (
        409,
        "INVALID_STATE_TRANSITION",
    )
    login = await _activate_and_sign_in(
        core_asgi, f"{fresh_code}.owner@acme.test", handover.json()["activation_code"]
    )
    assert login.status_code == 200, login.text
    assert login.json()["status"] == "mfa_enrolment_required", "MFA at first sign-in (LD-79)"

    audit = (await console.call("GET", "/audit", admin, params={"customer_id": run["customer_id"]})).json()[
        "items"
    ]
    actions = [entry["action"] for entry in audit]
    assert actions.count("platform.provisioning.step_completed") == 6
    assert {"platform.provisioning.started", "platform.provisioning.handover_revealed"} <= set(actions)


async def test_a_customer_is_invisible_to_core_until_the_run_activates_it(
    console: Console, admin: Staff, core: CoreRuntime, session_registry: RegistryService, fresh_code: str
) -> None:
    """Steps 1 to 6 leave the customer unroutable; only the snapshot for step 6 exists, and only
    during that step."""
    console.core.down = True  # stop the run at step 6
    run = await _start(console, admin, fresh_code)
    assert (run["status"], run["current_step"]) == ("failed", "initial_users")
    customer_id = UUID(run["customer_id"])
    assert await session_registry.get_snapshot(customer_id) is None
    assert await session_registry.get_provisioning_snapshot(customer_id) is None, (
        "not while the run is failed"
    )


# --------------------------------------------------------------------- failure and recovery
async def test_a_failed_job_stops_the_run_and_resume_continues_from_that_step(
    console: Console, admin: Staff, session_registry: RegistryService, fresh_code: str
) -> None:
    console.pipeline.fail_next = {"migrate"}
    run = await _start(console, admin, fresh_code)
    assert (run["status"], run["current_step"], run["attempts"]) == ("failed", "migrate", 1)
    assert "simulated job failure" in run["last_error"]
    customer = (await console.call("GET", f"/customers/{run['customer_id']}", admin)).json()
    assert (customer["status"], customer["licence_state"]) == ("provisioning", None)
    assert await session_registry.get_snapshot(UUID(run["customer_id"])) is None

    resumed = await console.call("POST", f"/provisioning-runs/{run['id']}/resume", admin)
    assert resumed.status_code == 202, resumed.text
    await console.settle()
    done = (await console.call("GET", f"/provisioning-runs/{run['id']}", admin)).json()
    assert (done["status"], done["current_step"], done["last_error"]) == ("completed", "done", None)
    assert console.pipeline.calls == ["provision", "migrate", "migrate"], "finished steps are not repeated"


async def test_a_lost_answer_from_core_is_safe_to_repeat(
    console: Console, admin: Staff, core_asgi: FastAPI, fresh_code: str
) -> None:
    """Core created the super admin but the answer never arrived: the resumed step issues a new
    activation code for the same person; the lost one stops working."""
    console.core.lose_next_response = True
    run = await _start(console, admin, fresh_code)
    assert (run["status"], run["current_step"]) == ("failed", "initial_users")
    assert (await console.call("POST", f"/provisioning-runs/{run['id']}/resume", admin)).status_code == 202
    await console.settle()
    done = (await console.call("GET", f"/provisioning-runs/{run['id']}", admin)).json()
    assert done["status"] == "completed", done
    code = (await console.call("POST", f"/provisioning-runs/{run['id']}/handover", admin)).json()[
        "activation_code"
    ]
    assert (await _activate_and_sign_in(core_asgi, f"{fresh_code}.owner@acme.test", code)).status_code == 200


async def test_resume_is_claimed_once_and_only_for_stopped_runs(
    console: Console, admin: Staff, fresh_code: str
) -> None:
    console.pipeline.fail_next = {"provision"}
    run = await _start(console, admin, fresh_code)
    assert (run["status"], run["current_step"]) == ("failed", "database")
    results = await asyncio.gather(
        console.call("POST", f"/provisioning-runs/{run['id']}/resume", admin),
        console.call("POST", f"/provisioning-runs/{run['id']}/resume", admin),
    )
    assert sorted(r.status_code for r in results) == [202, 409]
    await console.settle()
    assert (await console.call("GET", f"/provisioning-runs/{run['id']}", admin)).json()[
        "status"
    ] == "completed"
    # A completed run cannot be resumed; the same customer cannot be onboarded twice.
    assert _problem(await console.call("POST", f"/provisioning-runs/{run['id']}/resume", admin)) == (
        409,
        "INVALID_STATE_TRANSITION",
    )
    again = await console.call(
        "POST", "/provisioning-runs", admin, json=_request(fresh_code, console.clock.now())
    )
    assert _problem(again) == (409, "INVALID_STATE_TRANSITION")


async def test_gxp_customers_need_a_dedicated_instance(
    console: Console, admin: Staff, fresh_code: str
) -> None:
    refused = await console.call(
        "POST", "/provisioning-runs", admin, json=_request(fresh_code, console.clock.now(), gxp_mode=True)
    )
    assert _problem(refused) == (422, "VALIDATION_FAILED")


async def test_only_system_admins_provision(console: Console, fresh_code: str) -> None:
    from ims_platform.accounts import StaffRole  # noqa: PLC0415

    engineer = await console.staff(
        f"{fresh_code}.ravi@zongovita.test", StaffRole.SUPPORT_ENGINEER, name="Ravi"
    )
    refused = await console.call(
        "POST", "/provisioning-runs", engineer, json=_request(fresh_code, console.clock.now())
    )
    assert _problem(refused) == (403, "PERMISSION_DENIED")


# ------------------------------------------------------------- Core's provisioning endpoint
async def test_cores_provisioning_endpoint_trusts_only_the_platform_and_only_during_step_six(
    stack: Stack, core_asgi: FastAPI, customer_a: Customer, clock: ManualClock
) -> None:
    async def call(token: str | None) -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=core_asgi), base_url="http://core"
        ) as client:
            return await client.post(
                "/internal/v1/provisioning/super-admin",
                headers={"Authorization": f"Bearer {token}"} if token else {},
                json={"login_identifier": "x@acme.test", "display_name": "X"},
            )

    def token(service: str, customer_id: UUID) -> str:
        return ServiceTokenIssuer(service, stack.service_keys[service], clock).token_with(
            "ims-core-internal", {"cid": str(customer_id)}
        )

    assert _problem(await call(None)) == (401, "AUTH_REQUIRED")
    # Another service's valid token is not the Platform Service's.
    assert _problem(await call(token("tenant-web-bff", customer_a.id))) == (401, "AUTH_REQUIRED")
    # The Platform Service, for a customer that is not at step 6 of a run: nothing to reach.
    assert _problem(await call(token("ims-platform", customer_a.id))) == (404, "NOT_FOUND")


async def test_a_run_whose_executor_died_can_be_resumed_once_it_stops_progressing(
    console: Console, admin: Staff, fresh_code: str
) -> None:
    """A Platform Service instance that dies mid-run leaves it 'running'. It is not resumable
    while it may still be progressing, and becomes resumable after the stale period."""
    from ims_platform.provisioning import ProvisioningRequest  # noqa: PLC0415
    from ims_platform.registry import Actor  # noqa: PLC0415

    now = console.clock.now()
    run = await console.runtime.provisioning.start(
        Actor("platform_user:test"),
        ProvisioningRequest(
            code=fresh_code,
            legal_name="Acme",
            gxp_mode=False,
            placement=Placement.SHARED,
            licence_no=f"LIC-{fresh_code}-1",
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=365),
            grace_days=14,
            max_sites=5,
            max_users=50,
            modules=frozenset({"ims.core"}),
            super_admin_login=f"{fresh_code}.owner@acme.test",
            super_admin_name="Anita Rao",
            super_admin_email=None,
        ),
    )
    # Nothing executes it: as if its executor had died right after the start.
    early = await console.call("POST", f"/provisioning-runs/{run.id}/resume", admin)
    assert _problem(early) == (409, "INVALID_STATE_TRANSITION")
    console.clock.advance(seconds=16 * 60)
    admin = await console.sign_in_again(admin)
    assert (await console.call("POST", f"/provisioning-runs/{run.id}/resume", admin)).status_code == 202
    await console.settle()
    assert (await console.call("GET", f"/provisioning-runs/{run.id}", admin)).json()["status"] == "completed"
