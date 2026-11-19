"""Control-Plane guards of platform administration (Control-Plane migration 0003; LLD 4).

As the Platform Service's own role (platform_app), the way the service reaches the database.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ims_common.ids import uuid7
from ims_common.pg import create_pooler_engine, sqlstate_of
from tests.support.stack import PG_HOST, POOLER_PORT, Customer, Stack

pytestmark = pytest.mark.db

INSUFFICIENT_PRIVILEGE = "42501"
CHECK_VIOLATION = "23514"
UNIQUE_VIOLATION = "23505"


@pytest_asyncio.fixture
async def platform_engine(stack: Stack) -> AsyncIterator[AsyncEngine]:
    credential = await stack.platform_secrets.get("platform/db-app")
    engine = create_pooler_engine(
        host=PG_HOST,
        port=POOLER_PORT,
        database="ims_control_plane",
        user="platform_app",
        password=credential["password"],
        application_name="ims-tests-platform-schema",
        pool_size=1,
        max_overflow=0,
        pool_timeout_s=10,
        sslmode="disable",
    )
    yield engine
    await engine.dispose()


async def _fails(conn: AsyncConnection, sql: str, sqlstate: str, **params: Any) -> None:
    savepoint = await conn.begin_nested()
    try:
        await conn.execute(text(sql), params)
    except DBAPIError as exc:
        await savepoint.rollback()
        assert sqlstate_of(exc) == sqlstate, f"{sqlstate_of(exc)}: {exc.orig}"
        return
    await savepoint.rollback()
    raise AssertionError(f"expected SQLSTATE {sqlstate}: {sql}")


async def _staff(conn: AsyncConnection, role: str = "system_admin") -> Any:
    user_id = uuid7()
    await conn.execute(
        text(
            "INSERT INTO platform.platform_users (id, login_identifier, display_name, role, created_by, updated_by) "
            "VALUES (:id, :login, 'Staff', :role, 'test', 'test')"
        ),
        {"id": user_id, "login": f"{user_id}@zongovita.test", "role": role},
    )
    return user_id


async def test_staff_accounts_sessions_and_runs_are_never_deleted(
    platform_engine: AsyncEngine, customer_a: Customer
) -> None:
    async with platform_engine.begin() as conn:
        user = await _staff(conn)
        for table in (
            "platform.platform_users",
            "platform.platform_sessions",
            "platform.platform_recovery_codes",
            "platform.provisioning_runs",
        ):
            await _fails(conn, f"DELETE FROM {table} WHERE true", INSUFFICIENT_PRIVILEGE)
        await _fails(conn, "TRUNCATE platform.platform_users", INSUFFICIENT_PRIVILEGE)
        await _fails(conn, "DELETE FROM platform.platform_audit WHERE true", INSUFFICIENT_PRIVILEGE)
        assert user is not None
        await conn.rollback()


async def test_staff_roles_and_account_rules(platform_engine: AsyncEngine) -> None:
    async with platform_engine.begin() as conn:
        await _fails(
            conn,
            "INSERT INTO platform.platform_users (id, login_identifier, display_name, role, created_by, updated_by) "
            "VALUES (:id, 'x@z.test', 'X', 'customer_admin', 't', 't')",
            CHECK_VIOLATION,
            id=uuid7(),
        )
        user = await _staff(conn)
        # An active account has a password; identifiers are unique.
        await _fails(
            conn,
            "UPDATE platform.platform_users SET status = 'active' WHERE id = :id",
            CHECK_VIOLATION,
            id=user,
        )
        await _fails(
            conn,
            "INSERT INTO platform.platform_users (id, login_identifier, display_name, role, created_by, updated_by) "
            "SELECT :id, login_identifier, 'Y', 'system_admin', 't', 't' FROM platform.platform_users WHERE id = :u",
            UNIQUE_VIOLATION,
            id=uuid7(),
            u=user,
        )
        await conn.rollback()


async def test_one_run_per_customer_and_consistent_run_states(
    platform_engine: AsyncEngine, customer_a: Customer
) -> None:
    async with platform_engine.begin() as conn:
        insert = (
            "INSERT INTO platform.provisioning_runs (id, customer_id, request, requested_by, status, current_step, "
            "last_error, completed_at) VALUES (:id, :c, '{}', 'test', :status, :step, :error, :done)"
        )
        base = {"c": customer_a.id, "status": "running", "step": "register", "error": None, "done": None}
        await conn.execute(text(insert), {"id": uuid7(), **base})
        await _fails(conn, insert, UNIQUE_VIOLATION, id=uuid7(), **base)
        await conn.rollback()
    async with platform_engine.begin() as conn:
        # Completed means the last step with a completion time; failed carries its error.
        bad = [
            {"status": "completed", "step": "migrate", "error": None, "done": None},
            {"status": "failed", "step": "migrate", "error": None, "done": None},
            {"status": "running", "step": "teleport", "error": None, "done": None},
        ]
        for values in bad:
            await _fails(conn, insert, CHECK_VIOLATION, id=uuid7(), c=customer_a.id, **values)
        await conn.rollback()
