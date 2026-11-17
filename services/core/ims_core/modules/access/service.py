"""Access-control use cases (LLD 5.1, section 7, 12; AD-45, AD-46, LD-53).

Built-in rules of LLD section 7 enforced here (the database enforces those it can, see
migration 0003):

* Super Admin assignments change only by transfer: the generic assignment endpoints refuse that
  role, and the transfer locks the Super Admin role row, revokes and grants in one transaction.
* Reserved permissions stay with Super Admin; the Super Admin role cannot be edited or cloned.
* No lock-out of the super admin: other administrators cannot change, deactivate or re-assign
  that user until a transfer completes (decision I-27 for the super admin's own profile).
* No self-escalation: role and user managers cannot grant permissions they do not hold, at the
  sites the grant reaches (decision I-29).
* Every role, permission and assignment change is audited in the same transaction; in GxP mode
  it needs a reason (LD-82).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from ims_common.ids import uuid7
from ims_common.problem import DomainError
from ims_contracts.enums import PrincipalType
from ims_contracts.errors import ErrorCode, FieldError
from ims_contracts.licence import LicenceState
from ims_contracts.permissions import ALL_CODES, CATALOGUE, PERMISSIONS, RESERVED_TO_SUPER_ADMIN, RoleKind
from ims_core.kernel.grants import Grants, SiteScope
from ims_core.kernel.uow import UnitOfWork
from ims_core.modules.access import repository
from ims_core.modules.access.evaluation import grants_from
from ims_core.modules.identity.public import (
    ApiClientProfile,
    CreatedApiClient,
    CreatedUser,
    IdentityService,
    UserProfile,
    list_api_client_profiles,
    list_profiles,
    read_api_client_profile,
    read_profile,
    read_profiles,
)

if TYPE_CHECKING:
    from ims_common.clock import Clock

SUPER_ADMIN_BY_TRANSFER_ONLY = "the Super Admin role is assigned only by a super-admin transfer"
SUPER_ADMIN_PROTECTED = "the super admin cannot be changed by another user until a transfer completes"
SUPER_ADMIN_NOT_EDITABLE = "the Super Admin role holds every permission and cannot be edited"
NOT_HELD = "you cannot grant a permission you do not hold"


def _invalid(field: str, message: str) -> DomainError:
    return DomainError(ErrorCode.VALIDATION_FAILED, errors=[FieldError(field=field, message=message)])


def _actor(uow: UnitOfWork) -> UUID | None:
    return uow.ctx.principal.id if uow.ctx.principal else None


def _scope_json(scope: SiteScope) -> list[str] | None:
    return None if scope is None else sorted(str(site) for site in scope)


# ===================================================================================== views
@dataclass(frozen=True)
class EffectivePermission:
    code: str
    site_ids: list[str] | None


@dataclass(frozen=True)
class MeView:
    principal_id: UUID
    principal_type: str
    display_name: str
    email: str | None
    user_type_no: int | None
    is_super_admin: bool
    role_label: str
    permissions: list[EffectivePermission]
    licence_state: LicenceState
    grace_ends_at: datetime | None
    gxp_mode: bool
    modules: list[str]


@dataclass(frozen=True)
class AssignmentView:
    id: UUID
    role_id: UUID
    role_code: str
    role_name: str
    user_type_no: int | None
    site_id: UUID | None
    super_admin: bool
    granted_at: datetime


@dataclass(frozen=True)
class UserView:
    profile: UserProfile
    assignments: list[AssignmentView]
    is_super_admin: bool


@dataclass(frozen=True)
class RoleView:
    role: repository.RoleRow
    permissions: list[str]
    assigned_principals: int

    @property
    def editable(self) -> bool:
        return self.role.kind != RoleKind.SUPER_ADMIN


@dataclass(frozen=True)
class PermissionChange:
    principal_type: str
    principal_id: UUID
    display_name: str
    added: list[str]
    removed: list[str]
    rescoped: list[str]
    effective: list[EffectivePermission]


@dataclass(frozen=True)
class RolePermissionsResult:
    role: RoleView
    added: list[str]
    removed: list[str]
    preview: list[PermissionChange]


@dataclass(frozen=True)
class CreatedUserView:
    user: UserView
    activation_code: str
    activation_expires_at: datetime


@dataclass(frozen=True)
class ApiClientView:
    profile: ApiClientProfile
    assignments: list[AssignmentView]


@dataclass(frozen=True)
class AssignmentRequest:
    role_id: UUID
    site_id: UUID | None = None


def effective_list(grants: Grants) -> list[EffectivePermission]:
    return [EffectivePermission(code, _scope_json(scope)) for code, scope in grants.by_code.items()]


def role_label(roles: Sequence[repository.RoleRow], *, super_admin: bool) -> str:
    """Short label for the top bar: "Super Admin · Type 1", "User Type 3", "Type 2 · Auditor"."""
    types = sorted({role.user_type_no for role in roles if role.user_type_no is not None})
    custom = sorted({role.name for role in roles if role.kind == RoleKind.CUSTOM}, key=str.lower)
    parts = (["Super Admin"] if super_admin else []) + [f"Type {n}" for n in types] + custom
    if not super_admin and len(types) == 1 and not custom:
        return f"User Type {types[0]}"
    return " · ".join(parts) if parts else "No role assigned"


_CODE_CLEAN = re.compile(r"[^a-z0-9]+")


def role_code_from_name(name: str) -> str:
    """A role's natural key, derived from its name for custom roles."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    slug = _CODE_CLEAN.sub("_", ascii_name).strip("_")
    if not slug or not slug[0].isalpha():
        slug = f"role_{slug}".rstrip("_")
    return slug[:63]


# =================================================================================== service
async def compute_grants(uow: UnitOfWork, principal_type: str, principal_id: UUID) -> Grants:
    """Effective permissions read fresh from the database (no cache)."""
    rows = await repository.grant_rows(uow.db, principal_type, principal_id)
    super_admin = any(flag for _, flag, _ in rows)
    return grants_from(((site, code) for site, _, code in rows), super_admin=super_admin)


class AccessService:
    def __init__(self, identity: IdentityService, clock: Clock) -> None:
        self._identity = identity
        self._clock = clock

    compute_grants = staticmethod(compute_grants)

    # ------------------------------------------------------------------------------------ me
    async def me(self, uow: UnitOfWork) -> MeView:
        principal = uow.ctx.principal
        if principal is None or principal.type is not PrincipalType.USER:
            raise DomainError(ErrorCode.PERMISSION_DENIED, "only a user has a web session")
        profile = await read_profile(uow.db, principal.id)
        if profile is None:
            raise DomainError(ErrorCode.PRINCIPAL_INACTIVE)
        assignments = await repository.active_assignments(uow.db, "user", [principal.id])
        roles = await self._roles_by_id(uow, {a.role_id for a in assignments})
        held = [roles[a.role_id] for a in assignments if a.role_id in roles]
        super_admin = any(a.super_admin for a in assignments)
        types = sorted(role.user_type_no for role in held if role.user_type_no is not None)
        snapshot = uow.ctx.snapshot
        state = uow.ctx.licence_state
        return MeView(
            principal_id=profile.id,
            principal_type=principal.type.value,
            display_name=profile.display_name,
            email=profile.email,
            user_type_no=types[0] if types else None,
            is_super_admin=super_admin,
            role_label=role_label(held, super_admin=super_admin),
            permissions=effective_list(uow.grants),
            licence_state=state,
            grace_ends_at=snapshot.grace_ends_at if state is LicenceState.GRACE else None,
            gxp_mode=snapshot.gxp_mode,
            modules=sorted(snapshot.modules),
        )

    # -------------------------------------------------------------------------------- helpers
    @staticmethod
    async def _roles_by_id(uow: UnitOfWork, role_ids: Iterable[UUID]) -> dict[UUID, repository.RoleRow]:
        wanted = set(role_ids)
        if not wanted:
            return {}
        return {role.id: role for role in await repository.list_roles(uow.db) if role.id in wanted}

    @staticmethod
    def _assignment_views(
        assignments: Iterable[repository.AssignmentRow], roles: dict[UUID, repository.RoleRow]
    ) -> list[AssignmentView]:
        views = []
        for a in assignments:
            role = roles[a.role_id]
            views.append(
                AssignmentView(
                    id=a.id,
                    role_id=a.role_id,
                    role_code=role.code,
                    role_name=role.name,
                    user_type_no=role.user_type_no,
                    site_id=a.site_id,
                    super_admin=a.super_admin,
                    granted_at=a.granted_at,
                )
            )
        return views

    @staticmethod
    async def _super_admin_user(uow: UnitOfWork) -> UUID | None:
        holder = await repository.current_super_admin(uow.db)
        return holder.principal_id if holder is not None else None

    async def _protect_super_admin(
        self, uow: UnitOfWork, user_id: UUID, *, own_profile_edit: bool = False
    ) -> None:
        """No lock-out of the super admin (LLD 7): others cannot change that user."""
        if await self._super_admin_user(uow) != user_id:
            return
        if own_profile_edit and _actor(uow) == user_id:
            return
        raise DomainError(ErrorCode.PERMISSION_DENIED, SUPER_ADMIN_PROTECTED)

    @staticmethod
    def _require_can_grant(uow: UnitOfWork, codes: Iterable[str], site_id: UUID | None) -> None:
        """No self-escalation (LLD 7): the actor must hold every permission granted, at every
        site the grant reaches (``site_id`` None reaches every site)."""
        grants = uow.grants
        for code in sorted(set(codes)):
            if not grants.holds(code):
                raise DomainError(ErrorCode.PERMISSION_DENIED, f"{NOT_HELD}: {code}")
            if not PERMISSIONS[code].site_scoped:
                continue
            scope = grants.sites(code)
            if scope is None:
                continue
            if site_id is None or site_id not in scope:
                raise DomainError(ErrorCode.SITE_SCOPE_DENIED, f"{NOT_HELD} at that site: {code}")

    async def _role_codes(self, uow: UnitOfWork, role: repository.RoleRow) -> set[str]:
        if role.kind == RoleKind.SUPER_ADMIN:
            return set(ALL_CODES)
        return (await repository.role_permission_codes(uow.db, [role.id]))[role.id]

    # ---------------------------------------------------------------------------------- users
    async def _user_views(self, uow: UnitOfWork, profiles: Sequence[UserProfile]) -> list[UserView]:
        assignments = await repository.active_assignments(uow.db, "user", [p.id for p in profiles])
        roles = await self._roles_by_id(uow, {a.role_id for a in assignments})
        by_user: dict[UUID, list[repository.AssignmentRow]] = {}
        for a in assignments:
            by_user.setdefault(a.principal_id, []).append(a)
        return [
            UserView(
                profile=p,
                assignments=self._assignment_views(by_user.get(p.id, []), roles),
                is_super_admin=any(a.super_admin for a in by_user.get(p.id, [])),
            )
            for p in profiles
        ]

    async def list_users(
        self, uow: UnitOfWork, *, status: str | None, query: str | None, after: UUID | None, limit: int
    ) -> tuple[list[UserView], UUID | None]:
        profiles = await list_profiles(uow.db, status=status, query=query, after=after, limit=limit + 1)
        more = len(profiles) > limit
        page = profiles[:limit]
        return await self._user_views(uow, page), (page[-1].id if more and page else None)

    async def get_user(self, uow: UnitOfWork, user_id: UUID) -> UserView:
        profile = await read_profile(uow.db, user_id)
        if profile is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        return (await self._user_views(uow, [profile]))[0]

    async def create_user(
        self,
        uow: UnitOfWork,
        *,
        login_identifier: str,
        display_name: str,
        email: str | None,
        assignments: Sequence[AssignmentRequest],
        reason: str | None,
    ) -> CreatedUserView:
        """Reserve -> create -> activate (LLD 6.3) with the user's role assignments in the same
        transaction. Every assignment is checked before anything is written."""
        roles = await self._check_assignments(uow, assignments)
        created: CreatedUser = await self._identity.create_user(
            uow, login_identifier=login_identifier, display_name=display_name, email=email
        )
        for request in assignments:
            await self._insert_assignment(
                uow, "user", created.user_id, roles[request.role_id], request.site_id, reason
            )
        return CreatedUserView(
            user=await self.get_user(uow, created.user_id),
            activation_code=created.activation_code,
            activation_expires_at=created.activation_expires_at,
        )

    async def update_user(
        self, uow: UnitOfWork, user_id: UUID, *, expected_version: int, display_name: str, email: str | None
    ) -> UserView:
        await self._protect_super_admin(uow, user_id, own_profile_edit=True)
        await self._identity.update_profile(
            uow, user_id, expected_version=expected_version, display_name=display_name, email=email
        )
        return await self.get_user(uow, user_id)

    async def deactivate_user(self, uow: UnitOfWork, user_id: UUID, *, reason: str | None) -> UserView:
        if await self._super_admin_user(uow) == user_id:
            raise DomainError(
                ErrorCode.PERMISSION_DENIED, "the super admin cannot be deactivated before a transfer"
            )
        await self._identity.deactivate_user(uow, user_id, reason=reason)
        return await self.get_user(uow, user_id)

    # ---------------------------------------------------------------------------- assignments
    async def _check_assignments(
        self, uow: UnitOfWork, requests: Sequence[AssignmentRequest]
    ) -> dict[UUID, repository.RoleRow]:
        roles: dict[UUID, repository.RoleRow] = {}
        seen: set[tuple[UUID, UUID | None]] = set()
        for index, request in enumerate(requests):
            key = (request.role_id, request.site_id)
            if key in seen:
                raise _invalid(f"assignments[{index}]", "is listed twice")
            seen.add(key)
            role = roles.get(request.role_id) or await repository.read_role(uow.db, request.role_id)
            if role is None:
                raise _invalid(f"assignments[{index}].role_id", "no such role")
            if role.kind == RoleKind.SUPER_ADMIN:
                raise DomainError(ErrorCode.PERMISSION_DENIED, SUPER_ADMIN_BY_TRANSFER_ONLY)
            self._require_can_grant(uow, await self._role_codes(uow, role), request.site_id)
            roles[role.id] = role
        return roles

    async def _insert_assignment(
        self,
        uow: UnitOfWork,
        principal_type: str,
        principal_id: UUID,
        role: repository.RoleRow,
        site_id: UUID | None,
        reason: str | None,
    ) -> repository.AssignmentRow:
        if await repository.assignment_exists(
            uow.db, principal_type=principal_type, principal_id=principal_id, role_id=role.id, site_id=site_id
        ):
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION, "the principal already holds this role there"
            )
        row = await repository.insert_assignment(
            uow.db,
            assignment_id=uuid7(),
            principal_type=principal_type,
            principal_id=principal_id,
            role_id=role.id,
            site_id=site_id,
            actor=_actor(uow),
        )
        await uow.audit.record(
            action="iam.role_assignment.granted",
            entity_type="iam.role_assignment",
            entity_id=row.id,
            after={
                "principal_type": principal_type,
                "principal_id": principal_id,
                "role_id": role.id,
                "role_code": role.code,
                "site_id": site_id,
            },
            site_id=site_id,
            reason=reason,
            gmp_relevant=True,
        )
        return row

    async def assign(
        self,
        uow: UnitOfWork,
        *,
        principal_type: str,
        principal_id: UUID,
        role_id: UUID,
        site_id: UUID | None,
        reason: str | None,
    ) -> AssignmentView:
        if principal_type == "user":
            if await read_profile(uow.db, principal_id) is None:
                raise DomainError(ErrorCode.NOT_FOUND)
            await self._protect_super_admin(uow, principal_id)
        elif await read_api_client_profile(uow.db, principal_id) is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        roles = await self._check_assignments(uow, [AssignmentRequest(role_id=role_id, site_id=site_id)])
        role = roles[role_id]
        row = await self._insert_assignment(uow, principal_type, principal_id, role, site_id, reason)
        return self._assignment_views([row], roles)[0]

    async def revoke(self, uow: UnitOfWork, assignment_id: UUID, *, reason: str | None) -> None:
        assignment = await repository.lock_assignment(uow.db, assignment_id)
        if assignment is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        if assignment.revoked_at is not None:
            raise DomainError(ErrorCode.INVALID_STATE_TRANSITION, "the assignment is already revoked")
        if assignment.super_admin:
            raise DomainError(ErrorCode.PERMISSION_DENIED, SUPER_ADMIN_BY_TRANSFER_ONLY)
        if assignment.principal_type == "user":
            await self._protect_super_admin(uow, assignment.principal_id)
        await repository.revoke_assignment(uow.db, assignment_id, actor=_actor(uow), reason=reason)
        await uow.audit.record(
            action="iam.role_assignment.revoked",
            entity_type="iam.role_assignment",
            entity_id=assignment_id,
            before={
                "principal_type": assignment.principal_type,
                "principal_id": assignment.principal_id,
                "role_id": assignment.role_id,
                "site_id": assignment.site_id,
            },
            after={"revoked": True},
            site_id=assignment.site_id,
            reason=reason,
            gmp_relevant=True,
        )

    # ---------------------------------------------------------------------------------- roles
    async def list_roles(self, uow: UnitOfWork) -> list[RoleView]:
        roles = await repository.list_roles(uow.db)
        codes = await repository.role_permission_codes(uow.db, [r.id for r in roles])
        counts = await repository.assignment_counts(uow.db)
        return [
            RoleView(
                role=r,
                permissions=sorted(ALL_CODES if r.kind == RoleKind.SUPER_ADMIN else codes[r.id]),
                assigned_principals=counts.get(r.id, 0),
            )
            for r in roles
        ]

    async def get_role(self, uow: UnitOfWork, role_id: UUID) -> RoleView:
        for view in await self.list_roles(uow):
            if view.role.id == role_id:
                return view
        raise DomainError(ErrorCode.NOT_FOUND)

    @staticmethod
    def _check_codes(codes: Iterable[str]) -> set[str]:
        wanted = set(codes)
        unknown = sorted(wanted - ALL_CODES)
        if unknown:
            raise _invalid("permissions", f"unknown permissions: {', '.join(unknown)}")
        reserved = sorted(wanted & RESERVED_TO_SUPER_ADMIN)
        if reserved:
            raise _invalid("permissions", f"reserved to the Super Admin role: {', '.join(reserved)}")
        return wanted

    def _require_can_grant_to_role(self, uow: UnitOfWork, codes: Iterable[str]) -> None:
        # A role can be assigned at any site, so a granted site-scoped permission reaches every
        # site: the actor must hold it everywhere (decision I-29).
        self._require_can_grant(uow, codes, None)

    async def create_role(
        self,
        uow: UnitOfWork,
        *,
        name: str,
        code: str | None,
        description: str | None,
        permissions: Iterable[str],
        reason: str | None,
    ) -> RoleView:
        name = name.strip()
        if not name:
            raise _invalid("name", "is required")
        if len(name) > 100:
            raise _invalid("name", "is longer than 100 characters")
        role_code = code or role_code_from_name(name)
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,62}", role_code):
            raise _invalid("code", "lower-case letters, digits and underscores, starting with a letter")
        if await repository.role_code_taken(uow.db, role_code):
            raise _invalid("code" if code else "name", "a role with this code already exists")
        wanted = self._check_codes(permissions)
        self._require_can_grant_to_role(uow, wanted)
        role_id = uuid7()
        await repository.insert_role(
            uow.db, role_id=role_id, code=role_code, name=name, description=description, actor=_actor(uow)
        )
        await repository.add_role_permissions(uow.db, role_id, wanted, actor=_actor(uow))
        await uow.audit.record(
            action="iam.role.created",
            entity_type="iam.role",
            entity_id=role_id,
            after={
                "code": role_code,
                "name": name,
                "description": description,
                "permissions": sorted(wanted),
            },
            reason=reason,
            gmp_relevant=True,
        )
        return await self.get_role(uow, role_id)

    async def update_role(
        self,
        uow: UnitOfWork,
        role_id: UUID,
        *,
        expected_version: int,
        name: str,
        description: str | None,
        reason: str | None,
    ) -> RoleView:
        role = await repository.read_role(uow.db, role_id, lock=True)
        if role is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        if role.kind == RoleKind.SUPER_ADMIN:
            raise DomainError(ErrorCode.PERMISSION_DENIED, SUPER_ADMIN_NOT_EDITABLE)
        if role.version != expected_version:
            raise DomainError(ErrorCode.VERSION_CONFLICT)
        name = name.strip()
        if not name or len(name) > 100:
            raise _invalid("name", "is required and at most 100 characters")
        before = {"name": role.name, "description": role.description}
        after = {"name": name, "description": description}
        if before != after:
            await repository.update_role(
                uow.db, role_id, name=name, description=description, actor=_actor(uow)
            )
            await uow.audit.record(
                action="iam.role.updated",
                entity_type="iam.role",
                entity_id=role_id,
                before=before,
                after=after,
                reason=reason,
                gmp_relevant=True,
            )
        return await self.get_role(uow, role_id)

    async def _holders(self, uow: UnitOfWork, role_id: UUID) -> list[tuple[str, UUID]]:
        seen: dict[tuple[str, UUID], None] = {}
        for a in await repository.active_assignments_of_role(uow.db, role_id):
            seen[(a.principal_type, a.principal_id)] = None
        return list(seen)

    async def set_role_permissions(
        self,
        uow: UnitOfWork,
        role_id: UUID,
        *,
        expected_version: int,
        permissions: Iterable[str],
        reason: str | None,
    ) -> RolePermissionsResult:
        """Privilege-matrix submit (LLD 7): write the difference, audit each change and return an
        effective-permission preview per affected principal."""
        role = await repository.read_role(uow.db, role_id, lock=True)
        if role is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        if role.kind == RoleKind.SUPER_ADMIN:
            raise DomainError(ErrorCode.PERMISSION_DENIED, SUPER_ADMIN_NOT_EDITABLE)
        if role.version != expected_version:
            raise DomainError(ErrorCode.VERSION_CONFLICT)
        wanted = self._check_codes(permissions)
        current = (await repository.role_permission_codes(uow.db, [role_id]))[role_id]
        added = sorted(wanted - current)
        removed = sorted(current - wanted)
        self._require_can_grant_to_role(uow, added)

        holders = await self._holders(uow, role_id)
        before = {h: await self.compute_grants(uow, *h) for h in holders}
        if added or removed:
            await repository.add_role_permissions(uow.db, role_id, added, actor=_actor(uow))
            await repository.remove_role_permissions(uow.db, role_id, removed)
            await repository.touch_role(uow.db, role_id, actor=_actor(uow))
            for code, granted in [*((c, True) for c in added), *((c, False) for c in removed)]:
                await uow.audit.record(
                    action="iam.role.permissions_changed",
                    entity_type="iam.role",
                    entity_id=role_id,
                    before={"code": role.code, "permission": code, "granted": not granted},
                    after={"code": role.code, "permission": code, "granted": granted},
                    reason=reason,
                    gmp_relevant=True,
                )
        preview = await self._preview(uow, holders, before)
        return RolePermissionsResult(
            role=await self.get_role(uow, role_id), added=added, removed=removed, preview=preview
        )

    async def _preview(
        self, uow: UnitOfWork, holders: list[tuple[str, UUID]], before: dict[tuple[str, UUID], Grants]
    ) -> list[PermissionChange]:
        users = await read_profiles(uow.db, [pid for ptype, pid in holders if ptype == "user"])
        clients = (
            {c.id: c for c in await list_api_client_profiles(uow.db)}
            if any(ptype == "api_client" for ptype, _ in holders)
            else {}
        )
        changes = []
        for holder in holders:
            ptype, pid = holder
            old, new = before[holder], await self.compute_grants(uow, ptype, pid)
            old_codes, new_codes = set(old.by_code), set(new.by_code)
            name = (
                users[pid].display_name
                if ptype == "user" and pid in users
                else (clients[pid].name if pid in clients else str(pid))
            )
            changes.append(
                PermissionChange(
                    principal_type=ptype,
                    principal_id=pid,
                    display_name=name,
                    added=sorted(new_codes - old_codes),
                    removed=sorted(old_codes - new_codes),
                    rescoped=sorted(c for c in old_codes & new_codes if old.by_code[c] != new.by_code[c]),
                    effective=effective_list(new),
                )
            )
        return changes

    async def privilege_matrix(self, uow: UnitOfWork) -> tuple[list[RoleView], list[str]]:
        return await self.list_roles(uow), [p.code for p in CATALOGUE]

    # ---------------------------------------------------------------------------- super admin
    async def transfer_super_admin(
        self, uow: UnitOfWork, target_user_id: UUID, *, reason: str | None
    ) -> UserView:
        """POST super-admin/transfer (LLD 7): lock the Super Admin role row, revoke the current
        assignment and grant the new one in one transaction. Only the super admin holds
        access.super_admin.transfer, and the target must be an active user who can sign in."""
        role = await repository.lock_super_admin_role(uow.db)
        if role is None:
            raise RuntimeError("the Super Admin role is not seeded")
        holder = await repository.current_super_admin(uow.db)
        actor = _actor(uow)
        if holder is None or holder.principal_id != actor:
            # A concurrent transfer won the role-row lock first.
            raise DomainError(
                ErrorCode.PERMISSION_DENIED, "only the current super admin can transfer the role"
            )
        if target_user_id == actor:
            raise _invalid("user_id", "is already the super admin")
        target = await read_profile(uow.db, target_user_id, lock=True)
        if target is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        if target.status != "active":
            raise _invalid("user_id", "the new super admin must be an active user")
        await repository.revoke_assignment(uow.db, holder.id, actor=actor, reason="super-admin transfer")
        granted = await repository.insert_assignment(
            uow.db,
            assignment_id=uuid7(),
            principal_type="user",
            principal_id=target_user_id,
            role_id=role.id,
            site_id=None,
            actor=actor,
        )
        await uow.audit.record(
            action="iam.super_admin.transferred",
            entity_type="iam.role_assignment",
            entity_id=granted.id,
            before={"super_admin_user_id": holder.principal_id, "assignment_id": holder.id},
            after={"super_admin_user_id": target_user_id, "assignment_id": granted.id},
            reason=reason,
            gmp_relevant=True,
        )
        return await self.get_user(uow, target_user_id)

    async def bootstrap_super_admin(
        self, uow: UnitOfWork, *, login_identifier: str, display_name: str, email: str | None
    ) -> CreatedUserView:
        """Provisioning (LLD 6.6): the customer's first user, holding Super Admin and User Type 1
        at every site (decision I-30). Refused once a super admin exists."""
        if await repository.current_super_admin(uow.db) is not None:
            raise DomainError(ErrorCode.INVALID_STATE_TRANSITION, "the customer already has a super admin")
        roles = {role.code: role for role in await repository.list_roles(uow.db)}
        if "super_admin" not in roles or "user_type_1" not in roles:
            raise RuntimeError("seeded roles are missing: run the database pipeline first")
        created = await self._identity.create_user(
            uow, login_identifier=login_identifier, display_name=display_name, email=email
        )
        for code in ("super_admin", "user_type_1"):
            await self._insert_assignment(
                uow, "user", created.user_id, roles[code], None, "initial super admin (provisioning)"
            )
        return CreatedUserView(
            user=await self.get_user(uow, created.user_id),
            activation_code=created.activation_code,
            activation_expires_at=created.activation_expires_at,
        )

    # ---------------------------------------------------------------------------- API clients
    async def _client_views(
        self, uow: UnitOfWork, clients: Sequence[ApiClientProfile]
    ) -> list[ApiClientView]:
        assignments = await repository.active_assignments(uow.db, "api_client", [c.id for c in clients])
        roles = await self._roles_by_id(uow, {a.role_id for a in assignments})
        by_client: dict[UUID, list[repository.AssignmentRow]] = {}
        for a in assignments:
            by_client.setdefault(a.principal_id, []).append(a)
        return [
            ApiClientView(profile=c, assignments=self._assignment_views(by_client.get(c.id, []), roles))
            for c in clients
        ]

    async def list_api_clients(self, uow: UnitOfWork) -> list[ApiClientView]:
        return await self._client_views(uow, await list_api_client_profiles(uow.db))

    async def _client_view(self, uow: UnitOfWork, client_id: UUID) -> ApiClientView:
        profile = await read_api_client_profile(uow.db, client_id)
        if profile is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        return (await self._client_views(uow, [profile]))[0]

    async def create_api_client(
        self,
        uow: UnitOfWork,
        *,
        name: str,
        rate_limit_per_minute: int,
        assignments: Sequence[AssignmentRequest],
        reason: str | None,
    ) -> tuple[ApiClientView, str]:
        """An API credential with its role assignments (LD-13); never Super Admin."""
        roles = await self._check_assignments(uow, assignments)
        created: CreatedApiClient = await self._identity.create_api_client(
            uow, name=name, rate_limit_per_minute=rate_limit_per_minute
        )
        for request in assignments:
            await self._insert_assignment(
                uow, "api_client", created.client_id, roles[request.role_id], request.site_id, reason
            )
        return await self._client_view(uow, created.client_id), created.client_secret

    async def disable_api_client(self, uow: UnitOfWork, client_id: UUID) -> ApiClientView:
        await self._identity.disable_api_client(uow, client_id)
        return await self._client_view(uow, client_id)

    async def rotate_api_client_secret(self, uow: UnitOfWork, client_id: UUID) -> tuple[ApiClientView, str]:
        rotated = await self._identity.rotate_api_client_secret(uow, client_id)
        return await self._client_view(uow, client_id), rotated.client_secret
