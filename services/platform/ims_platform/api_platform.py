"""Platform administration API for the Platform Console (LLD 6.8 "/platform/v1": customers,
licences, provisioning-runs, users, audit; LLD 15; AD-04, AD-23).

ZongoVita staff only, through the console's own BFF; not routed from the internet. Every route
except the sign-in steps needs a live platform access token (MFA done). What a person may do
follows their staff role (HLD section 3): system admins manage customers, licences, provisioning
and staff; support engineers have no administration rights (their support sessions arrive with
unit 12). Every change is written to the append-only platform audit with the acting person.

Migration runs and break-glass requests, also listed under /platform/v1, arrive with units 14
and 12.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ims_common.problem import DomainError
from ims_contracts.enums import Placement
from ims_contracts.errors import ErrorCode
from ims_platform.accounts import AccountsService, SessionTokens, StaffPrincipal, StaffRole, StaffRow
from ims_platform.admin_queries import AdminQueries, CustomerView, LicenceView
from ims_platform.provisioning import ProvisioningRequest, ProvisioningService, RunRow
from ims_platform.registry import Actor, RegistryService

router = APIRouter(prefix="/platform/v1", tags=["platform"])
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- dependencies
def _accounts(request: Request) -> AccountsService:
    return request.app.state.runtime.accounts


def _queries(request: Request) -> AdminQueries:
    return request.app.state.runtime.queries


def _registry(request: Request) -> RegistryService:
    return request.app.state.runtime.registry


def _provisioning(request: Request) -> ProvisioningService:
    return request.app.state.runtime.provisioning


Accounts = Annotated[AccountsService, Depends(_accounts)]
Queries = Annotated[AdminQueries, Depends(_queries)]
Registry = Annotated[RegistryService, Depends(_registry)]
Provisioning = Annotated[ProvisioningService, Depends(_provisioning)]


async def _staff(request: Request) -> StaffPrincipal:
    return await request.app.state.runtime.accounts.authenticate(request.headers.get("authorization"))


Staff = Annotated[StaffPrincipal, Depends(_staff)]


async def _system_admin(staff: Staff) -> StaffPrincipal:
    if staff.role is not StaffRole.SYSTEM_ADMIN:
        raise DomainError(ErrorCode.PERMISSION_DENIED)
    return staff


SystemAdmin = Annotated[StaffPrincipal, Depends(_system_admin)]


def _actor(staff: StaffPrincipal, request: Request) -> Actor:
    return Actor(f"platform_user:{staff.user_id}", request_id=request.headers.get("x-request-id"))


def _json(body: Any, *, status_code: int = 200, headers: dict[str, str] | None = None) -> JSONResponse:
    if isinstance(body, BaseModel):
        body = body.model_dump(mode="json")
    return JSONResponse(body, status_code=status_code, headers=headers)


# ================================================================================ sign-in
class LoginBody(_Body):
    login_identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class ChallengeBody(_Body):
    challenge_token: str = Field(min_length=1, max_length=4096)


class MfaBody(_Body):
    challenge_token: str = Field(min_length=1, max_length=4096)
    code: str | None = Field(default=None, max_length=16)
    recovery_code: str | None = Field(default=None, max_length=32)


class RefreshBody(_Body):
    refresh_token: str = Field(min_length=1, max_length=4096)


class ActivateBody(_Body):
    login_identifier: str = Field(min_length=1, max_length=320)
    activation_code: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=1, max_length=256)


def _session(tokens: SessionTokens) -> JSONResponse:
    body: dict[str, Any] = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": "Bearer",
        "expires_in": tokens.expires_in,
        "refresh_expires_at": tokens.refresh_expires_at.isoformat(),
    }
    if tokens.recovery_codes is not None:
        body["recovery_codes"] = tokens.recovery_codes
    return _json(body, headers=NO_STORE)


@router.post("/auth/login")
async def login(body: LoginBody, accounts: Accounts) -> JSONResponse:
    challenge = await accounts.sign_in(body.login_identifier, body.password)
    return _json(
        {
            "status": "mfa_enrolment_required" if challenge.enrolment_required else "mfa_required",
            "challenge_token": challenge.challenge_token,
            "challenge_expires_in": challenge.expires_in,
        },
        headers=NO_STORE,
    )


@router.post("/auth/mfa/enrol")
async def enrol(body: ChallengeBody, accounts: Accounts) -> JSONResponse:
    enrolment = await accounts.begin_enrolment(body.challenge_token)
    return _json({"secret": enrolment.secret, "otpauth_uri": enrolment.otpauth_uri}, headers=NO_STORE)


@router.post("/auth/mfa")
async def mfa(body: MfaBody, accounts: Accounts) -> JSONResponse:
    return _session(
        await accounts.complete_mfa(body.challenge_token, code=body.code, recovery_code=body.recovery_code)
    )


@router.post("/auth/refresh")
async def refresh(body: RefreshBody, accounts: Accounts) -> JSONResponse:
    return _session(await accounts.refresh(body.refresh_token))


@router.post("/auth/logout", status_code=204)
async def logout(body: RefreshBody, accounts: Accounts) -> JSONResponse:
    await accounts.sign_out(body.refresh_token)
    return JSONResponse(None, status_code=204, headers=NO_STORE)


@router.post("/auth/activate", status_code=204)
async def activate(body: ActivateBody, accounts: Accounts) -> JSONResponse:
    await accounts.activate(body.login_identifier, body.activation_code, body.new_password)
    return JSONResponse(None, status_code=204, headers=NO_STORE)


# ===================================================================================== me
@router.get("/me")
async def me(staff: Staff) -> JSONResponse:
    return _json(
        {
            "id": str(staff.user_id),
            "display_name": staff.display_name,
            "login_identifier": staff.login_identifier,
            "email": staff.email,
            "role": staff.role.value,
        },
        headers={"Cache-Control": "no-store"},
    )


# ============================================================================== customers
def _licence(view: LicenceView | None) -> dict[str, Any] | None:
    if view is None:
        return None
    return {
        "id": str(view.id),
        "licence_no": view.licence_no,
        "record_status": view.record_status,
        "valid_from": view.valid_from.isoformat(),
        "valid_until": view.valid_until.isoformat(),
        "grace_days": view.grace_days,
        "max_sites": view.max_sites,
        "max_users": view.max_users,
        "modules": view.modules,
    }


def _customer(view: CustomerView) -> dict[str, Any]:
    return {
        "id": str(view.id),
        "code": view.code,
        "legal_name": view.legal_name,
        "status": view.status,
        "gxp_mode": view.gxp_mode,
        "gxp_locked": view.gxp_locked,
        "placement": view.placement,
        "created_at": view.created_at.isoformat(),
        "licence": _licence(view.licence),
        "licence_state": view.licence_state.value if view.licence_state else None,
        "grace_ends_at": view.grace_ends_at.isoformat() if view.grace_ends_at else None,
        "database": view.database,
        "provisioning_run": {**view.run, "id": str(view.run["id"])} if view.run else None,
    }


@router.get("/customers")
async def list_customers(_: SystemAdmin, queries: Queries) -> JSONResponse:
    return _json({"items": [_customer(c) for c in await queries.customers()]})


@router.get("/customers/{customer_id}")
async def get_customer(customer_id: UUID, _: SystemAdmin, queries: Queries) -> JSONResponse:
    view = await queries.customer(customer_id)
    if view is None:
        raise DomainError(ErrorCode.NOT_FOUND)
    return _json(_customer(view))


class ReasonBody(_Body):
    reason: str = Field(min_length=1, max_length=1000)


async def _customer_after(queries: AdminQueries, customer_id: UUID) -> JSONResponse:
    view = await queries.customer(customer_id)
    if view is None:
        raise DomainError(ErrorCode.NOT_FOUND)
    return _json(_customer(view))


@router.post("/customers/{customer_id}/suspend")
async def suspend_customer(
    customer_id: UUID,
    body: ReasonBody,
    staff: SystemAdmin,
    request: Request,
    registry: Registry,
    queries: Queries,
) -> JSONResponse:
    await registry.suspend_customer(customer_id, actor=_actor(staff, request), reason=body.reason)
    return await _customer_after(queries, customer_id)


@router.post("/customers/{customer_id}/reinstate")
async def reinstate_customer(
    customer_id: UUID,
    body: ReasonBody,
    staff: SystemAdmin,
    request: Request,
    registry: Registry,
    queries: Queries,
) -> JSONResponse:
    await registry.reinstate_customer(customer_id, actor=_actor(staff, request), reason=body.reason)
    return await _customer_after(queries, customer_id)


@router.post("/customers/{customer_id}/terminate")
async def terminate_customer(
    customer_id: UUID,
    body: ReasonBody,
    staff: SystemAdmin,
    request: Request,
    registry: Registry,
    queries: Queries,
) -> JSONResponse:
    await registry.terminate_customer(customer_id, actor=_actor(staff, request), reason=body.reason)
    return await _customer_after(queries, customer_id)


# =============================================================================== licences
class LicenceBody(_Body):
    licence_no: str = Field(min_length=1, max_length=64)
    valid_from: datetime
    valid_until: datetime
    grace_days: int = Field(default=14, ge=0, le=366)
    max_sites: int = Field(ge=1)
    max_users: int = Field(ge=1)
    modules: list[str] = Field(min_length=1, max_length=50)


@router.get("/customers/{customer_id}/licences")
async def list_licences(customer_id: UUID, _: SystemAdmin, queries: Queries) -> JSONResponse:
    if await queries.customer(customer_id) is None:
        raise DomainError(ErrorCode.NOT_FOUND)
    return _json({"items": [_licence(v) for v in await queries.licences(customer_id)]})


@router.post("/customers/{customer_id}/licences", status_code=201)
async def create_licence(
    customer_id: UUID,
    body: LicenceBody,
    staff: SystemAdmin,
    request: Request,
    registry: Registry,
    queries: Queries,
) -> JSONResponse:
    """A renewal or change of terms is a new draft licence; activating it supersedes the active
    one (decision I-06)."""
    licence_id = await registry.create_licence(
        customer_id=customer_id,
        licence_no=body.licence_no,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        grace_days=body.grace_days,
        max_sites=body.max_sites,
        max_users=body.max_users,
        modules=frozenset(body.modules),
        actor=_actor(staff, request),
    )
    created = next(v for v in await queries.licences(customer_id) if v.id == licence_id)
    return _json(_licence(created), status_code=201)


@router.post("/licences/{licence_id}/activate")
async def activate_licence(
    licence_id: UUID, staff: SystemAdmin, request: Request, registry: Registry, queries: Queries
) -> JSONResponse:
    customer_id = await queries.licence_customer(licence_id)
    if customer_id is None:
        raise DomainError(ErrorCode.NOT_FOUND)
    await registry.activate_licence(licence_id, actor=_actor(staff, request))
    return await _customer_after(queries, customer_id)


@router.get("/modules")
async def list_modules(_: SystemAdmin, queries: Queries) -> JSONResponse:
    return _json({"items": await queries.modules()})


# ====================================================================== provisioning runs
class CustomerPart(_Body):
    code: str = Field(min_length=2, max_length=30)
    legal_name: str = Field(min_length=1, max_length=200)
    gxp_mode: bool = False
    placement: Placement = Placement.SHARED


class PersonPart(_Body):
    login_identifier: str = Field(min_length=1, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)


class ProvisioningBody(_Body):
    customer: CustomerPart
    licence: LicenceBody
    super_admin: PersonPart


def _run(run: RunRow) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "customer_id": str(run.customer_id),
        "customer_code": run.request["customer"]["code"],
        "current_step": run.current_step,
        "status": run.status,
        "attempts": run.attempts,
        "last_error": run.last_error,
        "results": run.results,
        "super_admin": run.request["super_admin"]["login_identifier"],
        "super_admin_user_id": str(run.super_admin_user_id) if run.super_admin_user_id else None,
        "handover_available": run.handover_available,
        "requested_by": run.requested_by,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def _schedule(request: Request, provisioning: ProvisioningService, run_id: UUID) -> None:
    if request.app.state.runtime.settings.provisioning_in_background:
        provisioning.execute_in_background(run_id)


@router.get("/provisioning-runs")
async def list_runs(_: SystemAdmin, provisioning: Provisioning) -> JSONResponse:
    return _json({"items": [_run(r) for r in await provisioning.list_runs()]})


@router.get("/provisioning-runs/{run_id}")
async def get_run(run_id: UUID, _: SystemAdmin, provisioning: Provisioning) -> JSONResponse:
    return _json(_run(await provisioning.get_run(run_id)))


@router.post("/provisioning-runs", status_code=202)
async def start_run(
    body: ProvisioningBody, staff: SystemAdmin, request: Request, provisioning: Provisioning
) -> JSONResponse:
    """Onboard a customer (LLD 6.6, AD-28). The run continues in the background; poll it."""
    run = await provisioning.start(
        _actor(staff, request),
        ProvisioningRequest(
            code=body.customer.code,
            legal_name=body.customer.legal_name,
            gxp_mode=body.customer.gxp_mode,
            placement=body.customer.placement,
            licence_no=body.licence.licence_no,
            valid_from=body.licence.valid_from,
            valid_until=body.licence.valid_until,
            grace_days=body.licence.grace_days,
            max_sites=body.licence.max_sites,
            max_users=body.licence.max_users,
            modules=frozenset(body.licence.modules),
            super_admin_login=body.super_admin.login_identifier,
            super_admin_name=body.super_admin.display_name,
            super_admin_email=body.super_admin.email,
        ),
    )
    _schedule(request, provisioning, run.id)
    return _json(_run(run), status_code=202)


@router.post("/provisioning-runs/{run_id}/resume", status_code=202)
async def resume_run(
    run_id: UUID, staff: SystemAdmin, request: Request, provisioning: Provisioning
) -> JSONResponse:
    run = await provisioning.claim_for_resume(_actor(staff, request), run_id)
    _schedule(request, provisioning, run.id)
    return _json(_run(run), status_code=202)


@router.post("/provisioning-runs/{run_id}/handover")
async def reveal_handover(
    run_id: UUID, staff: SystemAdmin, request: Request, provisioning: Provisioning
) -> JSONResponse:
    """The super admin's one-time activation code, shown once to hand over (#21)."""
    handover = await provisioning.reveal_handover(_actor(staff, request), run_id)
    return _json(
        {
            "login_identifier": handover.login_identifier,
            "activation_code": handover.activation_code,
            "activation_expires_at": handover.activation_expires_at,
        },
        headers=NO_STORE,
    )


# ================================================================================== staff
def _user(row: StaffRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "login_identifier": row.login_identifier,
        "display_name": row.display_name,
        "email": row.email,
        "role": row.role,
        "status": row.status,
        "mfa_enrolled": row.mfa_enrolled_at is not None,
        "created_at": row.created_at.isoformat(),
        "version": row.version,
    }


class StaffBody(_Body):
    login_identifier: str = Field(min_length=1, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    role: Literal["system_admin", "support_engineer"]


class OptionalReason(_Body):
    reason: str | None = Field(default=None, max_length=1000)


@router.get("/users")
async def list_users(_: SystemAdmin, accounts: Accounts) -> JSONResponse:
    return _json({"items": [_user(u) for u in await accounts.list_users()]})


@router.post("/users", status_code=201)
async def create_user(
    body: StaffBody, staff: SystemAdmin, request: Request, accounts: Accounts
) -> JSONResponse:
    created = await accounts.create_user(
        _actor(staff, request),
        login_identifier=body.login_identifier,
        display_name=body.display_name,
        email=body.email,
        role=StaffRole(body.role),
    )
    return _json(
        {
            "user": _user(created.user),
            "activation_code": created.activation_code,
            "activation_expires_at": created.activation_expires_at.isoformat(),
        },
        status_code=201,
        headers=NO_STORE,
    )


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: UUID, body: OptionalReason, staff: SystemAdmin, request: Request, accounts: Accounts
) -> JSONResponse:
    return _json(_user(await accounts.deactivate_user(_actor(staff, request), user_id, reason=body.reason)))


# ================================================================================== audit
@router.get("/audit")
async def platform_audit(
    _: SystemAdmin,
    queries: Queries,
    customer_id: UUID | None = None,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> JSONResponse:
    rows = await queries.audit(customer_id=customer_id, before_seq=before_seq, limit=limit + 1)
    items = rows[:limit]
    return _json(
        {
            "items": [
                {
                    **{k: v for k, v in row.items() if k not in ("occurred_at", "customer_id")},
                    "occurred_at": row["occurred_at"].isoformat(),
                    "customer_id": str(row["customer_id"]) if row["customer_id"] else None,
                }
                for row in items
            ],
            "next_before_seq": items[-1]["seq"] if len(rows) > limit and items else None,
        }
    )
