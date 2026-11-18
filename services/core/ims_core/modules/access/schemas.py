"""Request and response bodies of the access endpoints (LLD 7, 12)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ims_contracts.licence import LicenceState


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


Reason = Field(default=None, max_length=1000, description="Reason for change; required in GxP mode (LD-82)")


# ------------------------------------------------------------------------------------- me
class MePrincipal(BaseModel):
    id: UUID
    type: Literal["user", "api_client", "support"]
    display_name: str
    email: str | None


class MePermission(BaseModel):
    code: str
    site_ids: list[UUID] | None = Field(description="null: every site")


class MeSite(BaseModel):
    id: UUID
    code: str
    name: str


class MeLicence(BaseModel):
    state: LicenceState
    grace_ends_at: datetime | None
    gxp_mode: bool
    modules: list[str]


class MeResponse(BaseModel):
    """GET /ui/v1/me: effective permissions per site and the licence state (LLD 7, 15).

    ``sites`` are the active sites the person works at (every active site when an assignment
    covers all sites); ``home_site_id`` is from their profile. ``unread_notifications`` is null
    until notifications exist (unit 10)."""

    principal: MePrincipal
    user_type_no: int | None
    is_super_admin: bool
    role_label: str
    sites: list[MeSite]
    home_site_id: UUID | None
    permissions: list[MePermission]
    licence: MeLicence
    unread_notifications: int | None


# ---------------------------------------------------------------------------- assignments
class AssignmentIn(_Body):
    role_id: UUID
    site_id: UUID | None = Field(default=None, description="null: every site")


class AssignmentOut(BaseModel):
    id: UUID
    role_id: UUID
    role_code: str
    role_name: str
    user_type_no: int | None
    site_id: UUID | None
    super_admin: bool
    granted_at: datetime


class CreateAssignment(_Body):
    principal_type: Literal["user", "api_client"]
    principal_id: UUID
    role_id: UUID
    site_id: UUID | None = None
    reason: str | None = Reason


class ReasonBody(_Body):
    reason: str | None = Reason


# ---------------------------------------------------------------------------------- users
class UserOut(BaseModel):
    id: UUID
    login_identifier: str
    display_name: str
    email: str | None
    department_id: UUID | None
    home_site_id: UUID | None
    status: Literal["invited", "active", "suspended", "deactivated"]
    mfa_enrolled: bool
    locked: bool
    is_super_admin: bool
    assignments: list[AssignmentOut]
    activation_expires_at: datetime | None
    last_active_at: datetime | None = Field(description="Latest sign-in or session refresh")
    created_at: datetime
    updated_at: datetime
    version: int


class UserPage(BaseModel):
    items: list[UserOut]
    next_cursor: str | None


class CreateUser(_Body):
    login_identifier: str = Field(min_length=1, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    department_id: UUID | None = None
    home_site_id: UUID | None = None
    assignments: list[AssignmentIn] = Field(default_factory=list, max_length=50)
    reason: str | None = Reason


class CreatedUserOut(BaseModel):
    """The activation code is shown once, to be handed to the user (#21, D-14)."""

    user: UserOut
    activation_code: str
    activation_expires_at: datetime


class UpdateUser(_Body):
    """The full editable profile: an omitted department or home site clears it."""

    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    department_id: UUID | None = None
    home_site_id: UUID | None = None


# ---------------------------------------------------------------------------------- roles
class RoleOut(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    kind: Literal["user_type", "super_admin", "custom"]
    user_type_no: int | None
    is_super_admin: bool
    editable: bool
    permissions: list[str]
    assigned_principals: int
    version: int


class CreateRole(_Body):
    name: str = Field(min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=63)
    description: str | None = Field(default=None, max_length=1000)
    permissions: list[str] = Field(default_factory=list, max_length=200)
    reason: str | None = Reason


class UpdateRole(_Body):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    reason: str | None = Reason


class SetRolePermissions(_Body):
    permissions: list[str] = Field(max_length=200)
    reason: str | None = Reason


class PermissionChangeOut(BaseModel):
    principal_type: Literal["user", "api_client"]
    principal_id: UUID
    display_name: str
    added: list[str]
    removed: list[str]
    rescoped: list[str]
    effective: list[MePermission]


class RolePermissionsOut(BaseModel):
    """The difference written, and each affected principal's effective permissions now."""

    role: RoleOut
    added: list[str]
    removed: list[str]
    preview: list[PermissionChangeOut]


class CatalogueEntry(BaseModel):
    code: str
    module: str
    site_scoped: bool
    reserved_to_super_admin: bool


class PrivilegeMatrix(BaseModel):
    permissions: list[CatalogueEntry]
    roles: list[RoleOut]


# ---------------------------------------------------------------------------- super admin
class TransferSuperAdmin(_Body):
    user_id: UUID
    reason: str | None = Reason


# ---------------------------------------------------------------------------- API clients
class ApiClientOut(BaseModel):
    id: UUID
    name: str
    rate_limit_per_minute: int
    status: Literal["active", "disabled"]
    assignments: list[AssignmentOut]
    created_at: datetime
    updated_at: datetime
    version: int


class CreateApiClient(_Body):
    name: str = Field(min_length=1, max_length=200)
    rate_limit_per_minute: int = Field(default=600, ge=1, le=600)
    assignments: list[AssignmentIn] = Field(default_factory=list, max_length=50)
    reason: str | None = Reason


class ApiClientSecretOut(BaseModel):
    """The secret is shown once and stored hashed (LLD 16)."""

    client: ApiClientOut
    client_id: str
    client_secret: str
