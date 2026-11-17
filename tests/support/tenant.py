"""A customer with real people in it, driven through the full Core application.

Sign-ins are real: activation code, password, TOTP enrolment and codes, access tokens. The super
admin is created the way provisioning creates it (LLD 6.6); everyone else through the user
endpoints, as an administrator would.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, FastAPI

from ims_common.clock import ManualClock
from ims_common.ids import uuid7
from ims_contracts.enums import LicenceModule
from ims_core.kernel.runtime import CoreRuntime
from ims_core.kernel.uow import unit_of_work
from ims_core.main import build_app
from ims_core.modules.access.public import RateLimits
from ims_core.modules.access.service import AccessService
from ims_core.modules.identity import domain
from tests.support.stack import Customer

PASSWORD = "correct horse battery staple"


@dataclass
class Person:
    user_id: UUID
    identifier: str
    secret: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@dataclass
class Tenant:
    app: FastAPI
    client: httpx.AsyncClient
    runtime: CoreRuntime
    clock: ManualClock
    customer: Customer
    super_admin: Person | None = None
    roles: dict[str, dict[str, Any]] = field(default_factory=dict)

    # ------------------------------------------------------------------------------- HTTP
    async def call(
        self,
        method: str,
        path: str,
        who: Person | None = None,
        *,
        json: Any = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        sent = dict(headers or {})
        if who is not None:
            sent.update(who.headers)
        if method in ("POST", "PUT", "PATCH", "DELETE") and not path.startswith("/ui/v1/auth/"):
            sent.setdefault("Idempotency-Key", f"test-{uuid7()}")
        return await self.client.request(method, path, json=json, headers=sent, params=params)

    async def get(self, path: str, who: Person, **kwargs: Any) -> httpx.Response:
        return await self.call("GET", path, who, **kwargs)

    async def post(self, path: str, who: Person | None, body: Any = None, **kwargs: Any) -> httpx.Response:
        return await self.call("POST", path, who, json=body if body is not None else {}, **kwargs)

    # ---------------------------------------------------------------------------- sign-in
    def code(self, secret: str) -> str:
        raw = base64.b32decode(secret + "=" * (-len(secret) % 8))
        return domain.totp_code(raw, domain.totp_step(self.clock.now()))

    async def activate_and_enrol(self, user_id: UUID, identifier: str, activation_code: str) -> Person:
        activated = await self.client.post(
            "/ui/v1/auth/activate",
            json={
                "login_identifier": identifier,
                "activation_code": activation_code,
                "new_password": PASSWORD,
            },
        )
        assert activated.status_code == 204, activated.text
        login = await self.client.post(
            "/ui/v1/auth/login", json={"login_identifier": identifier, "password": PASSWORD}
        )
        assert login.status_code == 200, login.text
        challenge = login.json()["challenge_token"]
        enrol = await self.client.post("/ui/v1/auth/mfa/enrol", json={"challenge_token": challenge})
        assert enrol.status_code == 200, enrol.text
        secret = enrol.json()["secret"]
        session = await self.client.post(
            "/ui/v1/auth/mfa", json={"challenge_token": challenge, "code": self.code(secret)}
        )
        assert session.status_code == 200, session.text
        return Person(
            user_id=user_id, identifier=identifier, secret=secret, token=session.json()["access_token"]
        )

    async def sign_in_again(self, person: Person) -> Person:
        """A later sign-in (next TOTP step: the previous one is spent)."""
        self.clock.advance(seconds=30)
        login = await self.client.post(
            "/ui/v1/auth/login", json={"login_identifier": person.identifier, "password": PASSWORD}
        )
        assert login.status_code == 200, login.text
        session = await self.client.post(
            "/ui/v1/auth/mfa",
            json={"challenge_token": login.json()["challenge_token"], "code": self.code(person.secret)},
        )
        assert session.status_code == 200, session.text
        person.token = session.json()["access_token"]
        return person

    # ------------------------------------------------------------------------------ setup
    async def bootstrap_super_admin(self, identifier: str, name: str = "Arjun Mehta") -> Person:
        """As provisioning does it (LLD 6.6): a system unit of work, no HTTP principal."""
        ctx = await self.runtime.credential_context(
            self.customer.id, module=LicenceModule.CORE, request_id="test-provisioning", source="system"
        )
        service: AccessService = self.app.state.access
        async with unit_of_work(self.runtime.router, ctx, self.clock) as uow:
            created = await service.bootstrap_super_admin(
                uow, login_identifier=identifier, display_name=name, email=None
            )
        self.super_admin = await self.activate_and_enrol(
            created.user.profile.id, identifier, created.activation_code
        )
        roles = await self.get("/ui/v1/roles", self.super_admin)
        assert roles.status_code == 200, roles.text
        self.roles = {role["code"]: role for role in roles.json()}
        return self.super_admin

    def role_id(self, code: str) -> str:
        return self.roles[code]["id"]

    async def create_person(
        self,
        identifier: str,
        assignments: Sequence[tuple[str, str | None]],
        *,
        by: Person | None = None,
        name: str = "Test User",
    ) -> Person:
        """Created by an administrator (the super admin unless ``by``), then signed in."""
        creator = by or self.super_admin
        assert creator is not None
        response = await self.post(
            "/ui/v1/users",
            creator,
            {
                "login_identifier": identifier,
                "display_name": name,
                "assignments": [
                    {"role_id": self.roles[code]["id"] if code in self.roles else code, "site_id": site}
                    for code, site in assignments
                ],
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        return await self.activate_and_enrol(UUID(body["user"]["id"]), identifier, body["activation_code"])

    async def refresh_roles(self) -> None:
        assert self.super_admin is not None
        roles = await self.get("/ui/v1/roles", self.super_admin)
        self.roles = {role["code"]: role for role in roles.json()}


def full_app(
    runtime: CoreRuntime, *, limits: RateLimits | None = None, routers: Sequence[APIRouter] = ()
) -> FastAPI:
    return build_app(runtime=runtime, run_change_feed=False, limits=limits, routers=routers)
