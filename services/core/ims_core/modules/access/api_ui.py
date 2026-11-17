"""Access endpoints of the UI API (LLD 12 route table, section 7).

| Endpoint                                                  | Rule                          |
| GET me                                                    | Authenticated                 |
| users (list, read, create, edit, deactivate)              | access.user.manage            |
| role-assignments (create, revoke; never Super Admin)      | access.user.manage            |
| roles, privilege-matrix, PUT roles/{id}/permissions       | access.role.manage            |
| super-admin/transfer                                      | access.super_admin.transfer   |
| api-clients                                               | access.api_client.manage      |
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ims_common.problem import DomainError
from ims_contracts.enums import LicenceModule
from ims_contracts.errors import ErrorCode, FieldError
from ims_contracts.permissions import CATALOGUE
from ims_core.kernel.authn import AUDIENCE_UI
from ims_core.kernel.routes import Authenticated, ImsRouter, Permission, Uow, declare
from ims_core.kernel.uow import UnitOfWork
from ims_core.kernel.versioning import IfMatch, set_etag
from ims_core.modules.access import schemas as s
from ims_core.modules.access.service import (
    AccessService,
    ApiClientView,
    AssignmentRequest,
    AssignmentView,
    EffectivePermission,
    RoleView,
    UserView,
)

router = ImsRouter(prefix="/ui/v1", audience=AUDIENCE_UI, module=LicenceModule.CORE, tags=["access"])

#: Responses carrying a one-time secret or activation code must not be cached (RFC 6749 5.1).
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}

USER_MANAGE = Permission("access.user.manage")
ROLE_MANAGE = Permission("access.role.manage")
CLIENT_MANAGE = Permission("access.api_client.manage")
TRANSFER = Permission("access.super_admin.transfer")


def get_access(request: Request) -> AccessService:
    return request.app.state.access


Access = Annotated[AccessService, Depends(get_access)]


# ----------------------------------------------------------------------------- converters
def _assignment(view: AssignmentView) -> s.AssignmentOut:
    return s.AssignmentOut(
        id=view.id,
        role_id=view.role_id,
        role_code=view.role_code,
        role_name=view.role_name,
        user_type_no=view.user_type_no,
        site_id=view.site_id,
        super_admin=view.super_admin,
        granted_at=view.granted_at,
    )


def _permission(view: EffectivePermission) -> s.MePermission:
    return s.MePermission(
        code=view.code, site_ids=[UUID(x) for x in view.site_ids] if view.site_ids else view.site_ids
    )


def _user(view: UserView, now_locked: bool = False) -> s.UserOut:
    p = view.profile
    return s.UserOut(
        id=p.id,
        login_identifier=p.login_identifier,
        display_name=p.display_name,
        email=p.email,
        status=p.status,  # type: ignore[arg-type]
        mfa_enrolled=p.mfa_enrolled_at is not None,
        locked=now_locked,
        is_super_admin=view.is_super_admin,
        assignments=[_assignment(a) for a in view.assignments],
        activation_expires_at=p.activation_expires_at if p.status == "invited" else None,
        last_active_at=p.last_active_at,
        created_at=p.created_at,
        updated_at=p.updated_at,
        version=p.version,
    )


def _user_out(view: UserView, uow: UnitOfWork) -> s.UserOut:
    locked_until = view.profile.locked_until
    return _user(view, now_locked=locked_until is not None and locked_until > uow.clock.now())


def _role(view: RoleView) -> s.RoleOut:
    r = view.role
    return s.RoleOut(
        id=r.id,
        code=r.code,
        name=r.name,
        description=r.description,
        kind=r.kind,  # type: ignore[arg-type]
        user_type_no=r.user_type_no,
        is_super_admin=r.is_super_admin_equivalent,
        editable=view.editable,
        permissions=view.permissions,
        assigned_principals=view.assigned_principals,
        version=r.version,
    )


def _client(view: ApiClientView) -> s.ApiClientOut:
    c = view.profile
    return s.ApiClientOut(
        id=c.id,
        name=c.name,
        rate_limit_per_minute=c.rate_limit_per_minute,
        status=c.status,  # type: ignore[arg-type]
        assignments=[_assignment(a) for a in view.assignments],
        created_at=c.created_at,
        updated_at=c.updated_at,
        version=c.version,
    )


def _json(model: BaseModel, *, status_code: int = 200, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(model.model_dump(mode="json"), status_code=status_code, headers=headers)


def _with_etag(model: BaseModel, version: int, *, status_code: int = 200) -> JSONResponse:
    response = _json(model, status_code=status_code)
    set_etag(response, version)
    return response


def _assignments(items: list[s.AssignmentIn]) -> list[AssignmentRequest]:
    return [AssignmentRequest(role_id=a.role_id, site_id=a.site_id) for a in items]


# -------------------------------------------------------------------------------------- me
@router.get("/me", response_model=s.MeResponse)
@declare(access=Authenticated(), read_only_ok=True)
async def me(uow: Uow, access: Access) -> JSONResponse:
    view = await access.me(uow)
    body = s.MeResponse(
        principal=s.MePrincipal(
            id=view.principal_id,
            type=view.principal_type,  # type: ignore[arg-type]
            display_name=view.display_name,
            email=view.email,
        ),
        user_type_no=view.user_type_no,
        is_super_admin=view.is_super_admin,
        role_label=view.role_label,
        sites=[],
        home_site_id=None,
        permissions=[_permission(p) for p in view.permissions],
        licence=s.MeLicence(
            state=view.licence_state,
            grace_ends_at=view.grace_ends_at,
            gxp_mode=view.gxp_mode,
            modules=view.modules,
        ),
        unread_notifications=None,
    )
    return _json(body, headers={"Cache-Control": "no-store"})


# ----------------------------------------------------------------------------------- users
def _cursor(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        raise DomainError(
            ErrorCode.VALIDATION_FAILED, errors=[FieldError(field="cursor", message="is not a valid cursor")]
        ) from None


@router.get("/users", response_model=s.UserPage)
@declare(access=USER_MANAGE, read_only_ok=True)
async def list_users(
    uow: Uow,
    access: Access,
    status: Annotated[str | None, Query(pattern="^(invited|active|suspended|deactivated)$")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> JSONResponse:
    users, next_after = await access.list_users(
        uow, status=status, query=q, after=_cursor(cursor), limit=limit
    )
    page = s.UserPage(
        items=[_user_out(u, uow) for u in users], next_cursor=str(next_after) if next_after else None
    )
    return _json(page)


@router.get("/users/{user_id}", response_model=s.UserOut)
@declare(access=USER_MANAGE, read_only_ok=True)
async def get_user(user_id: UUID, uow: Uow, access: Access) -> JSONResponse:
    view = await access.get_user(uow, user_id)
    return _with_etag(_user_out(view, uow), view.profile.version)


@router.post("/users", response_model=s.CreatedUserOut, status_code=201)
@declare(access=USER_MANAGE, read_only_ok=False)
async def create_user(body: s.CreateUser, uow: Uow, access: Access) -> JSONResponse:
    created = await access.create_user(
        uow,
        login_identifier=body.login_identifier,
        display_name=body.display_name,
        email=body.email,
        assignments=_assignments(body.assignments),
        reason=body.reason,
    )
    out = s.CreatedUserOut(
        user=_user_out(created.user, uow),
        activation_code=created.activation_code,
        activation_expires_at=created.activation_expires_at,
    )
    return _json(out, status_code=201, headers={**NO_STORE, "ETag": f'"{created.user.profile.version}"'})


@router.patch("/users/{user_id}", response_model=s.UserOut)
@declare(access=USER_MANAGE, read_only_ok=False)
async def update_user(
    user_id: UUID, body: s.UpdateUser, version: IfMatch, uow: Uow, access: Access
) -> JSONResponse:
    view = await access.update_user(
        uow, user_id, expected_version=version, display_name=body.display_name, email=body.email
    )
    return _with_etag(_user_out(view, uow), view.profile.version)


@router.post("/users/{user_id}/deactivate", response_model=s.UserOut)
@declare(access=USER_MANAGE, read_only_ok=False)
async def deactivate_user(user_id: UUID, body: s.ReasonBody, uow: Uow, access: Access) -> JSONResponse:
    view = await access.deactivate_user(uow, user_id, reason=body.reason)
    return _with_etag(_user_out(view, uow), view.profile.version)


# ------------------------------------------------------------------------ role assignments
@router.post("/role-assignments", response_model=s.AssignmentOut, status_code=201)
@declare(access=USER_MANAGE, read_only_ok=False)
async def create_assignment(body: s.CreateAssignment, uow: Uow, access: Access) -> JSONResponse:
    view = await access.assign(
        uow,
        principal_type=body.principal_type,
        principal_id=body.principal_id,
        role_id=body.role_id,
        site_id=body.site_id,
        reason=body.reason,
    )
    return _json(_assignment(view), status_code=201)


@router.post("/role-assignments/{assignment_id}/revoke", status_code=204)
@declare(access=USER_MANAGE, read_only_ok=False)
async def revoke_assignment(assignment_id: UUID, body: s.ReasonBody, uow: Uow, access: Access) -> Response:
    await access.revoke(uow, assignment_id, reason=body.reason)
    return Response(status_code=204)


# ----------------------------------------------------------------------------------- roles
@router.get("/roles", response_model=list[s.RoleOut])
@declare(access=ROLE_MANAGE, read_only_ok=True)
async def list_roles(uow: Uow, access: Access) -> JSONResponse:
    roles = await access.list_roles(uow)
    return JSONResponse([_role(r).model_dump(mode="json") for r in roles])


@router.get("/roles/{role_id}", response_model=s.RoleOut)
@declare(access=ROLE_MANAGE, read_only_ok=True)
async def get_role(role_id: UUID, uow: Uow, access: Access) -> JSONResponse:
    view = await access.get_role(uow, role_id)
    return _with_etag(_role(view), view.role.version)


@router.post("/roles", response_model=s.RoleOut, status_code=201)
@declare(access=ROLE_MANAGE, read_only_ok=False)
async def create_role(body: s.CreateRole, uow: Uow, access: Access) -> JSONResponse:
    view = await access.create_role(
        uow,
        name=body.name,
        code=body.code,
        description=body.description,
        permissions=body.permissions,
        reason=body.reason,
    )
    return _with_etag(_role(view), view.role.version, status_code=201)


@router.patch("/roles/{role_id}", response_model=s.RoleOut)
@declare(access=ROLE_MANAGE, read_only_ok=False)
async def update_role(
    role_id: UUID, body: s.UpdateRole, version: IfMatch, uow: Uow, access: Access
) -> JSONResponse:
    view = await access.update_role(
        uow,
        role_id,
        expected_version=version,
        name=body.name,
        description=body.description,
        reason=body.reason,
    )
    return _with_etag(_role(view), view.role.version)


@router.put("/roles/{role_id}/permissions", response_model=s.RolePermissionsOut)
@declare(access=ROLE_MANAGE, read_only_ok=False)
async def set_role_permissions(
    role_id: UUID, body: s.SetRolePermissions, version: IfMatch, uow: Uow, access: Access
) -> JSONResponse:
    result = await access.set_role_permissions(
        uow, role_id, expected_version=version, permissions=body.permissions, reason=body.reason
    )
    out = s.RolePermissionsOut(
        role=_role(result.role),
        added=result.added,
        removed=result.removed,
        preview=[
            s.PermissionChangeOut(
                principal_type=c.principal_type,  # type: ignore[arg-type]
                principal_id=c.principal_id,
                display_name=c.display_name,
                added=c.added,
                removed=c.removed,
                rescoped=c.rescoped,
                effective=[_permission(p) for p in c.effective],
            )
            for c in result.preview
        ],
    )
    return _with_etag(out, result.role.role.version)


@router.get("/privilege-matrix", response_model=s.PrivilegeMatrix)
@declare(access=ROLE_MANAGE, read_only_ok=True)
async def privilege_matrix(uow: Uow, access: Access) -> JSONResponse:
    roles, _ = await access.privilege_matrix(uow)
    matrix = s.PrivilegeMatrix(
        permissions=[
            s.CatalogueEntry(
                code=p.code,
                module=p.module,
                site_scoped=p.site_scoped,
                reserved_to_super_admin=p.reserved_to_super_admin,
            )
            for p in CATALOGUE
        ],
        roles=[_role(r) for r in roles],
    )
    return _json(matrix)


# ----------------------------------------------------------------------------- super admin
@router.post("/super-admin/transfer", response_model=s.UserOut)
@declare(access=TRANSFER, read_only_ok=False)
async def transfer_super_admin(body: s.TransferSuperAdmin, uow: Uow, access: Access) -> JSONResponse:
    view = await access.transfer_super_admin(uow, body.user_id, reason=body.reason)
    return _json(_user_out(view, uow))


# ----------------------------------------------------------------------------- API clients
@router.get("/api-clients", response_model=list[s.ApiClientOut])
@declare(access=CLIENT_MANAGE, read_only_ok=True)
async def list_api_clients(uow: Uow, access: Access) -> JSONResponse:
    return JSONResponse([_client(c).model_dump(mode="json") for c in await access.list_api_clients(uow)])


@router.post("/api-clients", response_model=s.ApiClientSecretOut, status_code=201)
@declare(access=CLIENT_MANAGE, read_only_ok=False)
async def create_api_client(body: s.CreateApiClient, uow: Uow, access: Access) -> JSONResponse:
    view, secret = await access.create_api_client(
        uow,
        name=body.name,
        rate_limit_per_minute=body.rate_limit_per_minute,
        assignments=_assignments(body.assignments),
        reason=body.reason,
    )
    out = s.ApiClientSecretOut(client=_client(view), client_id=str(view.profile.id), client_secret=secret)
    return _json(out, status_code=201, headers=NO_STORE)


@router.post("/api-clients/{client_id}/disable", response_model=s.ApiClientOut)
@declare(access=CLIENT_MANAGE, read_only_ok=False)
async def disable_api_client(client_id: UUID, uow: Uow, access: Access) -> JSONResponse:
    return _json(_client(await access.disable_api_client(uow, client_id)))


@router.post("/api-clients/{client_id}/rotate-secret", response_model=s.ApiClientSecretOut)
@declare(access=CLIENT_MANAGE, read_only_ok=False)
async def rotate_api_client_secret(client_id: UUID, uow: Uow, access: Access) -> JSONResponse:
    view, secret = await access.rotate_api_client_secret(uow, client_id)
    out = s.ApiClientSecretOut(client=_client(view), client_id=str(view.profile.id), client_secret=secret)
    return _json(out, headers=NO_STORE)
