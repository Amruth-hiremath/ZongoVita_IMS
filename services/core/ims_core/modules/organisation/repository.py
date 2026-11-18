"""SQL for org.sites, org.locations and org.departments. Nothing here decides anything."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import TextClause, text
from sqlalchemy.ext.asyncio import AsyncConnection

_RECORD = "created_at, updated_at, version"


# ------------------------------------------------------------------------------------ sites
@dataclass(frozen=True)
class SiteRow:
    id: UUID
    code: str
    name: str
    timezone: str
    status: str
    created_at: datetime
    updated_at: datetime
    version: int


_SITE = "id, code, name, timezone, status, " + _RECORD
_READ_SITE = text("SELECT " + _SITE + " FROM org.sites WHERE id = :id")  # noqa: S608 - fixed columns
_LOCK_SITE = text("SELECT " + _SITE + " FROM org.sites WHERE id = :id FOR UPDATE")  # noqa: S608
_LIST_SITES = text(
    "SELECT "  # noqa: S608 - fixed columns
    + _SITE
    + " FROM org.sites WHERE (CAST(:status AS text) IS NULL OR status = :status)"
    " AND (CAST(:after AS uuid) IS NULL OR id > :after) ORDER BY id LIMIT :limit"
)
_SITES_BY_ID = text("SELECT " + _SITE + " FROM org.sites WHERE id = ANY(:ids)")  # noqa: S608
_ACTIVE_SITES = text(
    "SELECT " + _SITE + " FROM org.sites WHERE status = 'active' ORDER BY upper(code)"  # noqa: S608
)


async def read_site(conn: AsyncConnection, site_id: UUID, *, lock: bool = False) -> SiteRow | None:
    row = (await conn.execute(_LOCK_SITE if lock else _READ_SITE, {"id": site_id})).mappings().first()
    return SiteRow(**row) if row else None


async def list_sites(
    conn: AsyncConnection, *, status: str | None, after: UUID | None, limit: int
) -> list[SiteRow]:
    rows = (await conn.execute(_LIST_SITES, {"status": status, "after": after, "limit": limit})).mappings()
    return [SiteRow(**row) for row in rows]


async def sites_by_id(conn: AsyncConnection, site_ids: Iterable[UUID]) -> dict[UUID, SiteRow]:
    ids = list(set(site_ids))
    if not ids:
        return {}
    return {row["id"]: SiteRow(**row) for row in (await conn.execute(_SITES_BY_ID, {"ids": ids})).mappings()}


async def active_sites(conn: AsyncConnection) -> list[SiteRow]:
    return [SiteRow(**row) for row in (await conn.execute(_ACTIVE_SITES)).mappings()]


async def count_licensed_sites(conn: AsyncConnection) -> int:
    """Staged and active sites count against the licence site limit (LLD 5.1)."""
    return int(
        (
            await conn.execute(text("SELECT count(*) FROM org.sites WHERE status IN ('staged', 'active')"))
        ).scalar_one()
    )


async def insert_site(
    conn: AsyncConnection,
    *,
    site_id: UUID,
    code: str,
    name: str,
    timezone: str,
    status: str,
    actor: UUID | None,
) -> None:
    await conn.execute(
        text(
            "INSERT INTO org.sites (id, code, name, timezone, status, created_by, updated_by) "
            "VALUES (:id, :code, :name, :timezone, :status, :actor, :actor)"
        ),
        {"id": site_id, "code": code, "name": name, "timezone": timezone, "status": status, "actor": actor},
    )


async def update_site(conn: AsyncConnection, site_id: UUID, *, actor: UUID | None, **fields: object) -> int:
    allowed = {"name", "timezone", "status"}
    return await _update(conn, "org.sites", allowed, site_id, actor, fields)


# -------------------------------------------------------------------------------- locations
@dataclass(frozen=True)
class LocationRow:
    id: UUID
    site_id: UUID
    code: str
    name: str
    is_default: bool
    status: str
    created_at: datetime
    updated_at: datetime
    version: int


_LOCATION = "id, site_id, code, name, is_default, status, " + _RECORD
_READ_LOCATION = text("SELECT " + _LOCATION + " FROM org.locations WHERE id = :id")  # noqa: S608
_LOCK_LOCATION = text("SELECT " + _LOCATION + " FROM org.locations WHERE id = :id FOR UPDATE")  # noqa: S608
_LIST_LOCATIONS = text(
    "SELECT "  # noqa: S608 - fixed columns
    + _LOCATION
    + " FROM org.locations WHERE (CAST(:site AS uuid) IS NULL OR site_id = :site)"
    " AND (CAST(:status AS text) IS NULL OR status = :status)"
    " AND (CAST(:after AS uuid) IS NULL OR id > :after) ORDER BY id LIMIT :limit"
)
_LOCK_DEFAULT = text(
    "SELECT " + _LOCATION + " FROM org.locations WHERE site_id = :site AND is_default FOR UPDATE"  # noqa: S608
)


async def read_location(
    conn: AsyncConnection, location_id: UUID, *, lock: bool = False
) -> LocationRow | None:
    row = (
        (await conn.execute(_LOCK_LOCATION if lock else _READ_LOCATION, {"id": location_id}))
        .mappings()
        .first()
    )
    return LocationRow(**row) if row else None


async def list_locations(
    conn: AsyncConnection, *, site_id: UUID | None, status: str | None, after: UUID | None, limit: int
) -> list[LocationRow]:
    params = {"site": site_id, "status": status, "after": after, "limit": limit}
    return [LocationRow(**row) for row in (await conn.execute(_LIST_LOCATIONS, params)).mappings()]


async def lock_default_location(conn: AsyncConnection, site_id: UUID) -> LocationRow | None:
    row = (await conn.execute(_LOCK_DEFAULT, {"site": site_id})).mappings().first()
    return LocationRow(**row) if row else None


async def insert_location(
    conn: AsyncConnection,
    *,
    location_id: UUID,
    site_id: UUID,
    code: str,
    name: str,
    is_default: bool,
    actor: UUID | None,
) -> None:
    await conn.execute(
        text(
            "INSERT INTO org.locations (id, site_id, code, name, is_default, created_by, updated_by) "
            "VALUES (:id, :site, :code, :name, :is_default, :actor, :actor)"
        ),
        {
            "id": location_id,
            "site": site_id,
            "code": code,
            "name": name,
            "is_default": is_default,
            "actor": actor,
        },
    )


async def update_location(
    conn: AsyncConnection, location_id: UUID, *, actor: UUID | None, **fields: object
) -> int:
    return await _update(conn, "org.locations", {"name", "status", "is_default"}, location_id, actor, fields)


# ------------------------------------------------------------------------------ departments
@dataclass(frozen=True)
class DepartmentRow:
    id: UUID
    code: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    version: int


_DEPARTMENT = "id, code, name, status, " + _RECORD
_READ_DEPARTMENT = text("SELECT " + _DEPARTMENT + " FROM org.departments WHERE id = :id")  # noqa: S608
_LOCK_DEPARTMENT = text("SELECT " + _DEPARTMENT + " FROM org.departments WHERE id = :id FOR UPDATE")  # noqa: S608
_LIST_DEPARTMENTS = text(
    "SELECT "  # noqa: S608 - fixed columns
    + _DEPARTMENT
    + " FROM org.departments WHERE (CAST(:status AS text) IS NULL OR status = :status)"
    " AND (CAST(:after AS uuid) IS NULL OR id > :after) ORDER BY id LIMIT :limit"
)


async def read_department(
    conn: AsyncConnection, department_id: UUID, *, lock: bool = False
) -> DepartmentRow | None:
    statement = _LOCK_DEPARTMENT if lock else _READ_DEPARTMENT
    row = (await conn.execute(statement, {"id": department_id})).mappings().first()
    return DepartmentRow(**row) if row else None


async def list_departments(
    conn: AsyncConnection, *, status: str | None, after: UUID | None, limit: int
) -> list[DepartmentRow]:
    params = {"status": status, "after": after, "limit": limit}
    return [DepartmentRow(**row) for row in (await conn.execute(_LIST_DEPARTMENTS, params)).mappings()]


async def insert_department(
    conn: AsyncConnection, *, department_id: UUID, code: str, name: str, actor: UUID | None
) -> None:
    await conn.execute(
        text(
            "INSERT INTO org.departments (id, code, name, created_by, updated_by) "
            "VALUES (:id, :code, :name, :actor, :actor)"
        ),
        {"id": department_id, "code": code, "name": name, "actor": actor},
    )


async def update_department(
    conn: AsyncConnection, department_id: UUID, *, actor: UUID | None, **fields: object
) -> int:
    return await _update(conn, "org.departments", {"name", "status"}, department_id, actor, fields)


# ----------------------------------------------------------------------------------- shared
_CODE_TAKEN: dict[str, TextClause] = {
    table: text(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE upper(code) = upper(:code))")  # noqa: S608
    for table in ("org.sites", "org.locations", "org.departments")
}


async def code_taken(conn: AsyncConnection, table: str, code: str) -> bool:
    return bool((await conn.execute(_CODE_TAKEN[table], {"code": code})).scalar_one())


async def _update(
    conn: AsyncConnection,
    table: str,
    allowed: set[str],
    row_id: UUID,
    actor: UUID | None,
    fields: dict[str, object],
) -> int:
    """Set allow-listed columns, bump the version; returns the new version."""
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"not an updatable column of {table}: {sorted(unknown)}")
    assignments = ", ".join(f"{name} = :{name}" for name in fields)
    statement = text(
        f"UPDATE {table} SET "  # noqa: S608 - table and columns from fixed allow-lists
        + assignments
        + ", updated_at = now(), updated_by = :actor, version = version + 1 WHERE id = :id RETURNING version"
    )
    return int((await conn.execute(statement, {**fields, "actor": actor, "id": row_id})).scalar_one())
