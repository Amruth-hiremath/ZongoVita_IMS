"""Core's internal endpoint for provisioning (LLD 6.6 step 6, AD-28; AD-13, AD-64).

The Platform Service orchestrates provisioning but holds no credential for customer data, so it
asks Core to create the new customer's super admin. Only the Platform Service's signed service
token is accepted (audience ims-core-internal); the customer comes from that token's claims and
never from the request (AD-21). Not routed from the internet.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ims_common.ids import uuid7
from ims_common.problem import DomainError
from ims_contracts.errors import ErrorCode
from ims_core.kernel.uow import unit_of_work

router = APIRouter(prefix="/internal/v1", tags=["internal"])


class SuperAdminBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login_identifier: str = Field(min_length=1, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)


@router.post("/provisioning/super-admin")
async def provision_super_admin(body: SuperAdminBody, request: Request) -> JSONResponse:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise DomainError(ErrorCode.AUTH_REQUIRED, "a platform service token is required")
    runtime = request.app.state.runtime
    ctx = await runtime.provisioning_context(token.strip(), request_id=f"provisioning-{uuid7()}")
    async with unit_of_work(runtime.router, ctx, runtime.clock) as uow:
        created = await request.app.state.access.provision_super_admin(
            uow, login_identifier=body.login_identifier, display_name=body.display_name, email=body.email
        )
    return JSONResponse(
        {
            "user_id": str(created.user_id),
            "activation_code": created.activation_code,
            "activation_expires_at": created.activation_expires_at.isoformat(),
        },
        headers={"Cache-Control": "no-store"},
    )
