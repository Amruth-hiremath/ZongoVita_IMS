"""Database guards of the organisation tables (LLD 5.1; migration 0004).

As the customer's application role through the pooler: the rules hold whatever SQL the
application sends.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ims_common.ids import uuid7
from ims_common.pg import sqlstate_of
from ims_platform.registry import RegistryService
from tests.support.stack import Customer, Stack, onboard_customer

pytestmark = pytest.mark.db

INSUFFICIENT_PRIVILEGE = "42501"
CHECK_VIOLATION = "23514"
UNIQUE_VIOLATION = "23505"
FOREIGN_KEY = "23503"
INTEGRITY = "23000"


@pytest_asyncio.fixture(scope="session")
async def org_db(stack: Stack, session_registry: RegistryService) -> Customer:
    return await onboard_customer(stack, session_registry, "org_db", now=datetime.now(UTC))


@pytest_asyncio.fixture
async def app_engine(stack: Stack, org_db: Customer) -> AsyncIterator[AsyncEngine]:
    engine = await stack.app_engine(org_db.db)
    yield engine
    await engine.dispose()


async def _fails(conn: AsyncConnection, sql: str, sqlstate: str, **params: Any) -> str:
    savepoint = await conn.begin_nested()
    try:
        await conn.execute(text(sql), params)
    except DBAPIError as exc:
        await savepoint.rollback()
        assert sqlstate_of(exc) == sqlstate, f"{sqlstate_of(exc)}: {exc.orig}"
        return str(exc.orig)
    await savepoint.rollback()
    raise AssertionError(f"expected SQLSTATE {sqlstate}: {sql}")


async def _site(
    conn: AsyncConnection, *, status: str = "active", with_default: bool = True
) -> tuple[UUID, UUID]:
    site_id, location_id = uuid7(), uuid7()
    code = f"S{site_id.hex[-10:]}"
    await conn.execute(
        text(
            "INSERT INTO org.sites (id, code, name, timezone, status) VALUES (:id, :code, 'Site', 'Asia/Kolkata', :s)"
        ),
        {"id": site_id, "code": code, "s": status},
    )
    await conn.execute(
        text(
            "INSERT INTO org.locations (id, site_id, code, name, is_default) VALUES (:id, :site, :code, 'Main', :d)"
        ),
        {"id": location_id, "site": site_id, "code": f"{code}-MAIN", "d": with_default},
    )
    return site_id, location_id


async def _commit_fails(engine: AsyncEngine, statements: list[tuple[str, dict[str, Any]]]) -> str:
    with pytest.raises(DBAPIError) as caught:
        async with engine.begin() as conn:
            for sql, params in statements:
                await conn.execute(text(sql), params)
    assert sqlstate_of(caught.value) == INTEGRITY, caught.value
    return str(caught.value.orig)


async def test_every_site_has_exactly_one_default_location(app_engine: AsyncEngine) -> None:
    # A site with no default location cannot be committed.
    site_id = uuid7()
    message = await _commit_fails(
        app_engine,
        [
            (
                "INSERT INTO org.sites (id, code, name, timezone) VALUES (:id, :code, 'Bare', 'Asia/Kolkata')",
                {"id": site_id, "code": f"B{site_id.hex[-10:]}"},
            )
        ],
    )
    assert "exactly one default location" in message

    async with app_engine.begin() as conn:
        site, main = await _site(conn)
    # Never two defaults.
    async with app_engine.begin() as conn:
        await _fails(
            conn,
            "INSERT INTO org.locations (id, site_id, code, name, is_default) VALUES (:id, :site, :code, 'X', true)",
            UNIQUE_VIOLATION,
            id=uuid7(),
            site=site,
            code=f"L{uuid7().hex[-10:]}",
        )
        # The default is active.
        await _fails(
            conn, "UPDATE org.locations SET status = 'inactive' WHERE id = :id", CHECK_VIOLATION, id=main
        )
        await conn.rollback()
    # Never none: unsetting the default without a replacement fails at commit.
    await _commit_fails(
        app_engine, [("UPDATE org.locations SET is_default = false WHERE id = :id", {"id": main})]
    )
    # Moving the default in one transaction is fine.
    async with app_engine.begin() as conn:
        other = uuid7()
        await conn.execute(
            text("INSERT INTO org.locations (id, site_id, code, name) VALUES (:id, :site, :code, 'Second')"),
            {"id": other, "site": site, "code": f"L{other.hex[-10:]}"},
        )
        await conn.execute(text("UPDATE org.locations SET is_default = false WHERE id = :id"), {"id": main})
        await conn.execute(text("UPDATE org.locations SET is_default = true WHERE id = :id"), {"id": other})


async def test_site_status_moves_only_along_defined_transitions(app_engine: AsyncEngine) -> None:
    async with app_engine.begin() as conn:
        staged, _ = await _site(conn, status="staged")
        active, _ = await _site(conn, status="active")
    async with app_engine.begin() as conn:
        await _fails(
            conn, "UPDATE org.sites SET status = 'staged' WHERE id = :id", CHECK_VIOLATION, id=active
        )
        await conn.execute(text("UPDATE org.sites SET status = 'active' WHERE id = :id"), {"id": staged})
        await conn.execute(text("UPDATE org.sites SET status = 'inactive' WHERE id = :id"), {"id": staged})
        await _fails(
            conn, "UPDATE org.sites SET status = 'staged' WHERE id = :id", CHECK_VIOLATION, id=staged
        )
        await conn.execute(text("UPDATE org.sites SET status = 'active' WHERE id = :id"), {"id": staged})
        await _fails(
            conn, "UPDATE org.sites SET status = 'paused' WHERE id = :id", CHECK_VIOLATION, id=staged
        )
        await conn.rollback()


async def test_timezones_codes_and_identity_are_guarded(app_engine: AsyncEngine) -> None:
    async with app_engine.begin() as conn:
        site, main = await _site(conn)
        code = (
            await conn.execute(text("SELECT code FROM org.sites WHERE id = :id"), {"id": site})
        ).scalar_one()
    async with app_engine.begin() as conn:
        message = await _fails(
            conn, "UPDATE org.sites SET timezone = 'Mars/Olympus' WHERE id = :id", CHECK_VIOLATION, id=site
        )
        assert "IANA timezone" in message
        await conn.execute(
            text("UPDATE org.sites SET timezone = 'Europe/Berlin' WHERE id = :id"), {"id": site}
        )
        # Codes are unique per customer whatever their case, and never change.
        await _fails(
            conn,
            "INSERT INTO org.sites (id, code, name, timezone) VALUES (:id, :code, 'Dup', 'UTC')",
            UNIQUE_VIOLATION,
            id=uuid7(),
            code=code.lower(),
        )
        await _fails(
            conn, "UPDATE org.sites SET code = 'RENAMED' WHERE id = :id", INSUFFICIENT_PRIVILEGE, id=site
        )
        await _fails(
            conn, "UPDATE org.locations SET code = 'RENAMED' WHERE id = :id", INSUFFICIENT_PRIVILEGE, id=main
        )
        await _fails(
            conn,
            "INSERT INTO org.sites (id, code, name, timezone) VALUES (:id, 'has space', 'Bad', 'UTC')",
            CHECK_VIOLATION,
            id=uuid7(),
        )
        # A location never moves to another site.
        other, _ = await _site(conn)
        await _fails(
            conn,
            "UPDATE org.locations SET site_id = :other WHERE id = :id",
            INSUFFICIENT_PRIVILEGE,
            other=other,
            id=main,
        )
        await conn.rollback()


async def test_nothing_is_deleted_and_keys_point_at_real_rows(app_engine: AsyncEngine) -> None:
    async with app_engine.begin() as conn:
        site, main = await _site(conn)
        department = uuid7()
        await conn.execute(
            text("INSERT INTO org.departments (id, code, name) VALUES (:id, :code, 'Maintenance')"),
            {"id": department, "code": f"D{department.hex[-10:]}"},
        )
    async with app_engine.begin() as conn:
        for table, row in (("org.sites", site), ("org.locations", main), ("org.departments", department)):
            await _fails(conn, f"DELETE FROM {table} WHERE id = :id", INSUFFICIENT_PRIVILEGE, id=row)
        # D-18, D-21: users and assignments now refer to real departments and sites.
        user = uuid7()
        await _fails(
            conn,
            "INSERT INTO iam.users (id, login_identifier, display_name, department_id) VALUES (:id, :l, 'U', :d)",
            FOREIGN_KEY,
            id=user,
            l=f"{user}@example.test",
            d=uuid7(),
        )
        await _fails(
            conn,
            "INSERT INTO iam.users (id, login_identifier, display_name, home_site_id) VALUES (:id, :l, 'U', :s)",
            FOREIGN_KEY,
            id=user,
            l=f"{user}@example.test",
            s=uuid7(),
        )
        await conn.execute(
            text(
                "INSERT INTO iam.users (id, login_identifier, display_name, department_id, home_site_id) "
                "VALUES (:id, :l, 'U', :d, :s)"
            ),
            {"id": user, "l": f"{user}@example.test", "d": department, "s": site},
        )
        role = (await conn.execute(text("SELECT id FROM iam.roles WHERE code = 'user_type_3'"))).scalar_one()
        await _fails(
            conn,
            "INSERT INTO iam.role_assignments (id, principal_type, principal_id, role_id, site_id) "
            "VALUES (:id, 'user', :u, :r, :s)",
            FOREIGN_KEY,
            id=uuid7(),
            u=user,
            r=role,
            s=uuid7(),
        )
        await conn.rollback()
