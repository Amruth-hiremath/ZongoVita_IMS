"""The Platform Service with IMS Core and the database pipeline, all in-process, for the platform
administration and provisioning tests.

* ``InProcessPipeline`` is the pipeline port run with the pipeline's own identity (every secret)
  inside the test process; it can be told to fail a job, as a CI/CD job would.
* ``Console`` signs ZongoVita staff in for real (password, then TOTP) and calls /platform/v1.
"""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI

from ims_common import auth_codes
from ims_common.clock import ManualClock
from ims_common.credentials import PasswordHasher
from ims_contracts.enums import Placement
from ims_core.kernel.runtime import CoreRuntime
from ims_db_pipeline.migrate import migrate_customer_database
from ims_db_pipeline.provision import provision_customer_database
from ims_platform.accounts import StaffRole
from ims_platform.main import create_app as create_platform_app
from ims_platform.provisioning import CorePort, DatabaseLocation, SuperAdminCreated
from ims_platform.registry import Actor
from ims_platform.runtime import PlatformRuntime
from ims_platform.runtime import build_runtime as build_platform_runtime
from ims_platform.settings import PlatformSettings
from tests.support.stack import PG_HOST, POOLER_PORT, Stack

PASSWORD = "staff correct horse battery"
CHEAP_HASHER = PasswordHasher(time_cost=1, memory_kib=1024, parallelism=1)


class JobFailed(RuntimeError):
    pass


@dataclass
class InProcessPipeline:
    stack: Stack
    #: Job names ("provision", "migrate") that fail on their next call, once each.
    fail_next: set[str] = field(default_factory=set)
    calls: list[str] = field(default_factory=list)

    async def provision_database(self, customer_code: str, placement: Placement) -> DatabaseLocation:
        self.calls.append("provision")
        if "provision" in self.fail_next:
            self.fail_next.discard("provision")
            raise JobFailed("provision-customer-db: simulated job failure")
        target = await provision_customer_database(
            self.stack.cluster, self.stack.pipeline_secrets, customer_code
        )
        return DatabaseLocation(
            cluster_ref=self.stack.cluster.cluster_ref,
            pooler_endpoint=self.stack.cluster.pooler_endpoint,
            database_name=target.database_name,
            app_role=target.app_role,
            secret_ref=target.app_secret_ref,
        )

    async def migrate_database(self, customer_code: str, placement: Placement) -> str:
        self.calls.append("migrate")
        if "migrate" in self.fail_next:
            self.fail_next.discard("migrate")
            raise JobFailed("migrate-customer-db: simulated job failure")
        outcome = await migrate_customer_database(
            self.stack.cluster, self.stack.pipeline_secrets, customer_code
        )
        return outcome.to_version


@dataclass
class FlakyCore:
    """Wraps the real Core port. ``lose_next_response`` lets the call reach Core and then fails,
    as a dropped connection would after Core committed: the step must be safe to repeat."""

    inner: CorePort
    lose_next_response: bool = False
    down: bool = False

    async def create_super_admin(
        self, customer_id: UUID, run_id: UUID, *, login_identifier: str, display_name: str, email: str | None
    ) -> SuperAdminCreated:
        if self.down:
            raise httpx.ConnectError("simulated: IMS Core unreachable")
        created = await self.inner.create_super_admin(
            customer_id, run_id, login_identifier=login_identifier, display_name=display_name, email=email
        )
        if self.lose_next_response:
            self.lose_next_response = False
            raise httpx.ReadError("simulated: the response was lost after Core committed")
        return created


def platform_settings(stack: Stack, **overrides: Any) -> PlatformSettings:
    return PlatformSettings(
        environment="test",
        db_pooler_host=PG_HOST,
        db_pooler_port=POOLER_PORT,
        db_sslmode="disable",
        db_pool_size=2,
        db_max_overflow=2,
        secrets_root=stack.secrets_root,
        object_store_root=stack.objects_root,
        core_base_url="http://core",
        **overrides,
    )


@dataclass
class Staff:
    user_id: UUID
    identifier: str
    secret: str
    token: str
    refresh_token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@dataclass
class Console:
    """A Platform Service with its pipeline and Core wired in, and an HTTP client to it."""

    runtime: PlatformRuntime
    app: FastAPI
    client: httpx.AsyncClient
    clock: ManualClock
    pipeline: InProcessPipeline
    core: FlakyCore

    def code(self, secret: str) -> str:
        raw = base64.b32decode(secret + "=" * (-len(secret) % 8))
        return auth_codes.totp_code(raw, auth_codes.totp_step(self.clock.now()))

    async def staff(
        self, identifier: str, role: StaffRole = StaffRole.SYSTEM_ADMIN, name: str = "Kiran Desai"
    ) -> Staff:
        """Created, activated, enrolled and signed in."""
        created = await self.runtime.accounts.create_user(
            Actor("system:test"), login_identifier=identifier, display_name=name, email=None, role=role
        )
        activated = await self.client.post(
            "/platform/v1/auth/activate",
            json={
                "login_identifier": identifier,
                "activation_code": created.activation_code,
                "new_password": PASSWORD,
            },
        )
        assert activated.status_code == 204, activated.text
        login = await self.client.post(
            "/platform/v1/auth/login", json={"login_identifier": identifier, "password": PASSWORD}
        )
        assert login.status_code == 200, login.text
        assert login.json()["status"] == "mfa_enrolment_required"
        challenge = login.json()["challenge_token"]
        secret = (
            await self.client.post("/platform/v1/auth/mfa/enrol", json={"challenge_token": challenge})
        ).json()["secret"]
        session = await self.client.post(
            "/platform/v1/auth/mfa", json={"challenge_token": challenge, "code": self.code(secret)}
        )
        assert session.status_code == 200, session.text
        body = session.json()
        return Staff(created.user.id, identifier, secret, body["access_token"], body["refresh_token"])

    async def sign_in_again(self, staff: Staff) -> Staff:
        """A later sign-in, for example after the test moved the clock past the session."""
        self.clock.advance(seconds=30)  # the next TOTP step: the previous one is spent
        login = await self.client.post(
            "/platform/v1/auth/login", json={"login_identifier": staff.identifier, "password": PASSWORD}
        )
        assert login.status_code == 200, login.text
        session = await self.client.post(
            "/platform/v1/auth/mfa",
            json={"challenge_token": login.json()["challenge_token"], "code": self.code(staff.secret)},
        )
        assert session.status_code == 200, session.text
        staff.token, staff.refresh_token = session.json()["access_token"], session.json()["refresh_token"]
        return staff

    async def call(self, method: str, path: str, staff: Staff | None, **kwargs: Any) -> httpx.Response:
        headers = {**(staff.headers if staff else {}), **kwargs.pop("headers", {})}
        return await self.client.request(method, f"/platform/v1{path}", headers=headers, **kwargs)

    async def settle(self) -> None:
        """Wait for provisioning runs started in the background."""
        await self.runtime.provisioning.wait_for_background()


@asynccontextmanager
async def console_for(
    stack: Stack, clock: ManualClock, core_runtime: CoreRuntime, core_app: FastAPI
) -> AsyncIterator[Console]:
    """The Platform Service under test calls the in-process Core app; Core reaches this same
    Control-Plane database through its own registry link."""
    pipeline = InProcessPipeline(stack)
    from ims_common.service_auth import ServiceTokenIssuer  # noqa: PLC0415
    from ims_common.tokens import KeySet  # noqa: PLC0415
    from ims_platform.provisioning import HttpCore  # noqa: PLC0415

    core_http = httpx.AsyncClient(transport=httpx.ASGITransport(app=core_app), base_url="http://core")
    keys = KeySet.from_secret(await stack.pipeline_secrets.get("services/ims-platform/signing"))
    core = FlakyCore(HttpCore(core_http, ServiceTokenIssuer("ims-platform", keys, clock)))
    runtime = await build_platform_runtime(
        platform_settings(stack),
        secrets=stack.platform_secrets,
        object_store=stack.object_store,
        clock=clock,
        pipeline=pipeline,
        core=core,
        hasher=CHEAP_HASHER,
    )
    app = create_platform_app(runtime=runtime, run_bundle_publisher=False)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://platform"
        ) as client:
            yield Console(runtime=runtime, app=app, client=client, clock=clock, pipeline=pipeline, core=core)
    finally:
        await runtime.aclose()
        await core_http.aclose()
