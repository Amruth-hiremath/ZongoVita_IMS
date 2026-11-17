"""SQL for roles, role permissions and role assignments. Nothing here decides anything."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


# --------------------------------------------------------------------------- access version
async def access_version(conn: AsyncConnection) -> int:
    return int((await conn.execute(text("SELECT version FROM iam.access_version"))).scalar_one())


# ------------------------------------------------------------------------------------ roles
@dataclass(frozen=True)
class RoleRow:
    id: UUID
    code: str
    name: str
    description: str | None
    kind: str
    user_type_no: int | None
    is_super_admin_equivalent: bool
    created_at: datetime
    updated_at: datetime
    version: int


_ROLE_COLUMNS = (
    "id, code, name, description, kind, user_type_no, is_super_admin_equivalent, "
    "created_at, updated_at, version"
)
_LIST_ROLES = text(
    "SELECT "  # noqa: S608 - fixed columns
    + _ROLE_COLUMNS
    + " FROM iam.roles ORDER BY is_super_admin_equivalent DESC, user_type_no NULLS LAST, lower(name), id"
)
_READ_ROLE = text("SELECT " + _ROLE_COLUMNS + " FROM iam.roles WHERE id = :id")  # noqa: S608
_LOCK_ROLE = text("SELECT " + _ROLE_COLUMNS + " FROM iam.roles WHERE id = :id FOR UPDATE")  # noqa: S608
_LOCK_SUPER_ADMIN_ROLE = text(
    "SELECT " + _ROLE_COLUMNS + " FROM iam.roles WHERE is_super_admin_equivalent FOR UPDATE"  # noqa: S608
)


async def list_roles(conn: AsyncConnection) -> list[RoleRow]:
    return [RoleRow(**row) for row in (await conn.execute(_LIST_ROLES)).mappings()]


async def read_role(conn: AsyncConnection, role_id: UUID, *, lock: bool = False) -> RoleRow | None:
    row = (await conn.execute(_LOCK_ROLE if lock else _READ_ROLE, {"id": role_id})).mappings().first()
    return RoleRow(**row) if row else None


async def lock_super_admin_role(conn: AsyncConnection) -> RoleRow | None:
    """Serialises super-admin transfers (LLD 7: "locks the role row")."""
    row = (await conn.execute(_LOCK_SUPER_ADMIN_ROLE)).mappings().first()
    return RoleRow(**row) if row else None


async def role_code_taken(conn: AsyncConnection, code: str) -> bool:
    return bool(
        (
            await conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM iam.roles WHERE code = :code)"), {"code": code}
            )
        ).scalar_one()
    )


async def insert_role(
    conn: AsyncConnection, *, role_id: UUID, code: str, name: str, description: str | None, actor: UUID | None
) -> None:
    await conn.execute(
        text(
            "INSERT INTO iam.roles (id, code, name, description, kind, created_by, updated_by) "
            "VALUES (:id, :code, :name, :description, 'custom', :actor, :actor)"
        ),
        {"id": role_id, "code": code, "name": name, "description": description, "actor": actor},
    )


async def update_role(
    conn: AsyncConnection, role_id: UUID, *, name: str, description: str | None, actor: UUID | None
) -> int:
    return int(
        (
            await conn.execute(
                text(
                    "UPDATE iam.roles SET name = :name, description = :description, updated_at = now(), "
                    "updated_by = :actor, version = version + 1 WHERE id = :id RETURNING version"
                ),
                {"id": role_id, "name": name, "description": description, "actor": actor},
            )
        ).scalar_one()
    )


async def touch_role(conn: AsyncConnection, role_id: UUID, *, actor: UUID | None) -> int:
    """New row version after its permissions changed (the matrix submits with If-Match)."""
    return int(
        (
            await conn.execute(
                text(
                    "UPDATE iam.roles SET updated_at = now(), updated_by = :actor, version = version + 1 "
                    "WHERE id = :id RETURNING version"
                ),
                {"id": role_id, "actor": actor},
            )
        ).scalar_one()
    )


# ------------------------------------------------------------------------- role permissions
async def role_permission_codes(conn: AsyncConnection, role_ids: Iterable[UUID]) -> dict[UUID, set[str]]:
    ids = list(role_ids)
    found: dict[UUID, set[str]] = {role_id: set() for role_id in ids}
    if not ids:
        return found
    rows = await conn.execute(
        text("SELECT role_id, permission_code FROM iam.role_permissions WHERE role_id = ANY(:ids)"),
        {"ids": ids},
    )
    for role_id, code in rows:
        found[role_id].add(code)
    return found


async def add_role_permissions(
    conn: AsyncConnection, role_id: UUID, codes: Iterable[str], *, actor: UUID | None
) -> None:
    params = [{"role_id": role_id, "code": code, "actor": actor} for code in sorted(codes)]
    if params:
        await conn.execute(
            text(
                "INSERT INTO iam.role_permissions (role_id, permission_code, granted_by) "
                "VALUES (:role_id, :code, :actor)"
            ),
            params,
        )


async def remove_role_permissions(conn: AsyncConnection, role_id: UUID, codes: Iterable[str]) -> None:
    removed = sorted(codes)
    if removed:
        await conn.execute(
            text(
                "DELETE FROM iam.role_permissions WHERE role_id = :role_id AND permission_code = ANY(:codes)"
            ),
            {"role_id": role_id, "codes": removed},
        )


# ------------------------------------------------------------------------------ assignments
@dataclass(frozen=True)
class AssignmentRow:
    id: UUID
    principal_type: str
    principal_id: UUID
    role_id: UUID
    site_id: UUID | None
    super_admin: bool
    granted_at: datetime
    granted_by: UUID | None
    revoked_at: datetime | None


_ASSIGNMENT_COLUMNS = (
    "id, principal_type, principal_id, role_id, site_id, super_admin, granted_at, granted_by, revoked_at"
)
_ACTIVE_FOR = text(
    "SELECT "  # noqa: S608 - fixed columns
    + _ASSIGNMENT_COLUMNS
    + " FROM iam.role_assignments WHERE revoked_at IS NULL AND principal_type = :ptype"
    " AND principal_id = ANY(:ids) ORDER BY granted_at, id"
)
_ACTIVE_FOR_ROLE = text(
    "SELECT "  # noqa: S608 - fixed columns
    + _ASSIGNMENT_COLUMNS
    + " FROM iam.role_assignments WHERE revoked_at IS NULL AND role_id = :role_id ORDER BY granted_at, id"
)
_READ_ASSIGNMENT = text(
    "SELECT " + _ASSIGNMENT_COLUMNS + " FROM iam.role_assignments WHERE id = :id FOR UPDATE"  # noqa: S608
)
_INSERT_ASSIGNMENT = text(
    "INSERT INTO iam.role_assignments (id, principal_type, principal_id, role_id, site_id, "  # noqa: S608
    "granted_by) VALUES (:id, :ptype, :pid, :role_id, :site_id, :actor) RETURNING " + _ASSIGNMENT_COLUMNS
)
_CURRENT_SUPER_ADMIN = text(
    "SELECT "  # noqa: S608 - fixed columns
    + _ASSIGNMENT_COLUMNS
    + " FROM iam.role_assignments WHERE super_admin AND revoked_at IS NULL"
)


async def active_assignments(
    conn: AsyncConnection, principal_type: str, principal_ids: Iterable[UUID]
) -> list[AssignmentRow]:
    ids = list(principal_ids)
    if not ids:
        return []
    rows = (await conn.execute(_ACTIVE_FOR, {"ptype": principal_type, "ids": ids})).mappings()
    return [AssignmentRow(**row) for row in rows]


async def active_assignments_of_role(conn: AsyncConnection, role_id: UUID) -> list[AssignmentRow]:
    return [
        AssignmentRow(**row)
        for row in (await conn.execute(_ACTIVE_FOR_ROLE, {"role_id": role_id})).mappings()
    ]


async def lock_assignment(conn: AsyncConnection, assignment_id: UUID) -> AssignmentRow | None:
    row = (await conn.execute(_READ_ASSIGNMENT, {"id": assignment_id})).mappings().first()
    return AssignmentRow(**row) if row else None


async def current_super_admin(conn: AsyncConnection) -> AssignmentRow | None:
    row = (await conn.execute(_CURRENT_SUPER_ADMIN)).mappings().first()
    return AssignmentRow(**row) if row else None


async def insert_assignment(
    conn: AsyncConnection,
    *,
    assignment_id: UUID,
    principal_type: str,
    principal_id: UUID,
    role_id: UUID,
    site_id: UUID | None,
    actor: UUID | None,
) -> AssignmentRow:
    row = (
        (
            await conn.execute(
                _INSERT_ASSIGNMENT,
                {
                    "id": assignment_id,
                    "ptype": principal_type,
                    "pid": principal_id,
                    "role_id": role_id,
                    "site_id": site_id,
                    "actor": actor,
                },
            )
        )
        .mappings()
        .one()
    )
    return AssignmentRow(**row)


async def assignment_exists(
    conn: AsyncConnection, *, principal_type: str, principal_id: UUID, role_id: UUID, site_id: UUID | None
) -> bool:
    return bool(
        (
            await conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM iam.role_assignments WHERE revoked_at IS NULL "
                    "AND principal_type = :ptype AND principal_id = :pid AND role_id = :role_id "
                    "AND site_id IS NOT DISTINCT FROM :site_id)"
                ),
                {"ptype": principal_type, "pid": principal_id, "role_id": role_id, "site_id": site_id},
            )
        ).scalar_one()
    )


async def revoke_assignment(
    conn: AsyncConnection, assignment_id: UUID, *, actor: UUID | None, reason: str | None
) -> None:
    """granted_at and revoked_at both come from the database clock, so they always compare."""
    await conn.execute(
        text(
            "UPDATE iam.role_assignments SET revoked_at = now(), revoked_by = :actor, "
            "revoke_reason = :reason WHERE id = :id"
        ),
        {"id": assignment_id, "actor": actor, "reason": reason},
    )


async def assignment_counts(conn: AsyncConnection) -> dict[UUID, int]:
    rows = await conn.execute(
        text(
            "SELECT role_id, count(DISTINCT (principal_type, principal_id)) FROM iam.role_assignments "
            "WHERE revoked_at IS NULL GROUP BY role_id"
        )
    )
    return {role_id: int(count) for role_id, count in rows}


async def grant_rows(
    conn: AsyncConnection, principal_type: str, principal_id: UUID
) -> list[tuple[UUID | None, bool, str | None]]:
    """(site, super admin, permission) for every active assignment: what evaluation needs."""
    rows = await conn.execute(
        text(
            "SELECT ra.site_id, ra.super_admin, rp.permission_code FROM iam.role_assignments ra "
            "LEFT JOIN iam.role_permissions rp ON rp.role_id = ra.role_id "
            "WHERE ra.revoked_at IS NULL AND ra.principal_type = :ptype AND ra.principal_id = :pid"
        ),
        {"ptype": principal_type, "pid": principal_id},
    )
    return [(site_id, bool(super_admin), code) for site_id, super_admin, code in rows]
