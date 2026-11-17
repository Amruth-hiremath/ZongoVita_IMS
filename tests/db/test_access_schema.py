"""Database guards of access control (LLD 5.1, section 7 built-in rules; LLD 17 "Exactly one super
admin": concurrent transfers, revoking the last assignment, reserved-permission grants and
API-client super admins fail).

Everything runs as the customer's application role through the pooler, as the application
would; the rules hold whatever SQL the application sends.
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
from ims_contracts.permissions import CATALOGUE, SEEDED_ROLES
from ims_db_pipeline.migrate import migrate_customer_database
from ims_platform.registry import RegistryService
from tests.support.stack import Customer, Stack, onboard_customer

pytestmark = pytest.mark.db

INSUFFICIENT_PRIVILEGE = "42501"
CHECK_VIOLATION = "23514"
UNIQUE_VIOLATION = "23505"
INTEGRITY = "23000"
FOREIGN_KEY = "23503"


@pytest_asyncio.fixture(scope="session")
async def acl(stack: Stack, session_registry: RegistryService) -> Customer:
    """A customer of its own: these tests create the super admin directly in SQL."""
    return await onboard_customer(stack, session_registry, "acl_db", now=datetime.now(UTC))


@pytest_asyncio.fixture
async def app_engine(stack: Stack, acl: Customer) -> AsyncIterator[AsyncEngine]:
    engine = await stack.app_engine(acl.db)
    yield engine
    await engine.dispose()


async def _fails(conn: AsyncConnection, sql: str, sqlstate: str, **params: Any) -> str:
    """Run in a savepoint and expect the given SQLSTATE; the outer transaction stays usable."""
    savepoint = await conn.begin_nested()
    try:
        await conn.execute(text(sql), params)
    except DBAPIError as exc:
        await savepoint.rollback()
        assert sqlstate_of(exc) == sqlstate, f"{sqlstate_of(exc)}: {exc.orig}"
        return str(exc.orig)
    await savepoint.rollback()
    raise AssertionError(f"expected SQLSTATE {sqlstate}: {sql}")


async def _role(conn: AsyncConnection, code: str) -> UUID:
    return (await conn.execute(text("SELECT id FROM iam.roles WHERE code = :c"), {"c": code})).scalar_one()


async def _user(conn: AsyncConnection, status: str = "invited") -> UUID:
    user_id = uuid7()
    await conn.execute(
        text(
            "INSERT INTO iam.users (id, login_identifier, display_name, status, password_hash) "
            "VALUES (:id, :login, 'Test', :status, CASE WHEN :status = 'invited' THEN NULL ELSE 'x' END)"
        ),
        {"id": user_id, "login": f"{user_id}@example.test", "status": status},
    )
    return user_id


async def _assign(conn: AsyncConnection, user_id: UUID, role_id: UUID, site_id: UUID | None = None) -> UUID:
    assignment_id = uuid7()
    await conn.execute(
        text(
            "INSERT INTO iam.role_assignments (id, principal_type, principal_id, role_id, site_id) "
            "VALUES (:id, 'user', :pid, :role, :site)"
        ),
        {"id": assignment_id, "pid": user_id, "role": role_id, "site": site_id},
    )
    return assignment_id


async def _ensure_super_admin(engine: AsyncEngine) -> UUID:
    """The committed super admin of this customer (created once)."""
    async with engine.begin() as conn:
        existing = (
            await conn.execute(
                text("SELECT principal_id FROM iam.role_assignments WHERE super_admin AND revoked_at IS NULL")
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        holder = await _user(conn, "active")
        await _assign(conn, holder, await _role(conn, "super_admin"))
        return holder


# --------------------------------------------------------------------------- the seed
async def test_catalogue_and_seeded_roles_equal_the_code(
    stack: Stack, acl: Customer, app_engine: AsyncEngine
) -> None:
    async with app_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT code, module, site_scoped, reserved_to_super_admin FROM iam.permission_catalog")
        )
        assert {tuple(r) for r in rows} == {
            (p.code, p.module, p.site_scoped, p.reserved_to_super_admin) for p in CATALOGUE
        }
        roles = {
            r.code: r
            for r in await conn.execute(
                text("SELECT id, code, kind, user_type_no, is_super_admin_equivalent FROM iam.roles")
            )
        }
        assert set(roles) == {r.code for r in SEEDED_ROLES}
        for seeded in SEEDED_ROLES:
            row = roles[seeded.code]
            assert (row.kind, row.user_type_no, row.is_super_admin_equivalent) == (
                seeded.kind.value,
                seeded.user_type_no,
                seeded.is_super_admin,
            )
            granted = set(
                (
                    await conn.execute(
                        text("SELECT permission_code FROM iam.role_permissions WHERE role_id = :id"),
                        {"id": row.id},
                    )
                ).scalars()
            )
            # Super Admin holds every permission by definition and has no rows (I-25).
            assert granted == (set() if seeded.is_super_admin else seeded.permissions), seeded.code

    async with app_engine.begin() as conn:
        await _fails(
            conn,
            "INSERT INTO iam.permission_catalog VALUES ('a.b.c', 'a', false, false)",
            INSUFFICIENT_PRIVILEGE,
        )
        await _fails(
            conn, "UPDATE iam.permission_catalog SET site_scoped = NOT site_scoped", INSUFFICIENT_PRIVILEGE
        )
        await _fails(conn, "UPDATE iam.access_version SET version = 1", INSUFFICIENT_PRIVILEGE)
        await conn.rollback()


async def test_catalogue_rebuild_removes_stale_codes_and_keeps_customer_edits(
    stack: Stack, acl: Customer, app_engine: AsyncEngine
) -> None:
    migrator = await stack.migration_engine(acl.db)
    try:
        async with migrator.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO iam.permission_catalog VALUES ('catalog.legacy.thing', 'catalog', false, false)"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO iam.role_permissions (role_id, permission_code) "
                    "SELECT id, 'catalog.legacy.thing' FROM iam.roles WHERE code = 'user_type_1'"
                )
            )
    finally:
        await migrator.dispose()
    # A customer edit of a seeded role: Type 2 no longer approves transfers.
    async with app_engine.begin() as conn:
        await conn.execute(
            text(
                "DELETE FROM iam.role_permissions WHERE permission_code = 'transfers.transfer.approve' "
                "AND role_id = (SELECT id FROM iam.roles WHERE code = 'user_type_2')"
            )
        )

    outcome = await migrate_customer_database(stack.cluster, stack.pipeline_secrets, acl.code)
    assert outcome.access is not None
    assert outcome.access.removed == ["catalog.legacy.thing"]
    assert outcome.access.revoked_from_roles == [("user_type_1", "catalog.legacy.thing")]
    assert outcome.access.roles_created == []

    async with app_engine.connect() as conn:
        audit = (
            await conn.execute(
                text(
                    "SELECT actor_type, after->>'permission', reason FROM audit.audit_log "
                    "WHERE action = 'iam.role.permissions_changed' AND source = 'system'"
                )
            )
        ).all()
        assert [tuple(a) for a in audit] == [
            ("system", "catalog.legacy.thing", "permission removed from the catalogue by a release")
        ]
        kept = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM iam.role_permissions rp JOIN iam.roles r ON r.id = rp.role_id "
                    "WHERE r.code = 'user_type_2' AND rp.permission_code = 'transfers.transfer.approve'"
                )
            )
        ).scalar_one()
        assert kept == 0, "a release never re-seeds an edited role"

    again = await migrate_customer_database(stack.cluster, stack.pipeline_secrets, acl.code)
    assert again.access is not None and again.access.unchanged


# --------------------------------------------------------------- roles and permissions
async def test_reserved_permissions_and_the_super_admin_role_are_guarded(app_engine: AsyncEngine) -> None:
    async with app_engine.begin() as conn:
        super_role = await _role(conn, "super_admin")
        type1 = await _role(conn, "user_type_1")
        message = await _fails(
            conn,
            "INSERT INTO iam.role_permissions (role_id, permission_code) VALUES (:r, 'access.support.grant')",
            INSUFFICIENT_PRIVILEGE,
            r=type1,
        )
        assert "reserved to the Super Admin" in message
        await _fails(
            conn,
            "INSERT INTO iam.role_permissions (role_id, permission_code) VALUES (:r, 'catalog.item.view')",
            INSUFFICIENT_PRIVILEGE,
            r=super_role,
        )
        await _fails(
            conn, "UPDATE iam.roles SET name = 'Boss' WHERE id = :r", INSUFFICIENT_PRIVILEGE, r=super_role
        )
        await _fails(
            conn, "UPDATE iam.roles SET code = 'renamed' WHERE id = :r", INSUFFICIENT_PRIVILEGE, r=type1
        )
        await _fails(
            conn,
            "UPDATE iam.roles SET kind = 'custom', user_type_no = NULL WHERE id = :r",
            INSUFFICIENT_PRIVILEGE,
            r=type1,
        )
        # No second Super Admin role, and no clone that claims to be one.
        await _fails(
            conn,
            "INSERT INTO iam.roles (id, code, name, kind, is_super_admin_equivalent) "
            "VALUES (:id, 'boss', 'Boss', 'super_admin', true)",
            UNIQUE_VIOLATION,
            id=uuid7(),
        )
        await _fails(
            conn,
            "INSERT INTO iam.roles (id, code, name, kind, is_super_admin_equivalent) "
            "VALUES (:id, 'boss', 'Boss', 'custom', true)",
            CHECK_VIOLATION,
            id=uuid7(),
        )
        await _fails(
            conn,
            "INSERT INTO iam.roles (id, code, name, kind, user_type_no) VALUES (:id, 'type1b', 'T', 'user_type', 1)",
            UNIQUE_VIOLATION,
            id=uuid7(),
        )
        # Seeded user types stay editable (#10).
        await conn.execute(
            text("UPDATE iam.roles SET name = 'Stores' WHERE id = :r"),
            {"r": await _role(conn, "user_type_3")},
        )
        await conn.rollback()


# ------------------------------------------------------------------- one super admin
async def test_exactly_one_super_admin_always(app_engine: AsyncEngine) -> None:
    holder = await _ensure_super_admin(app_engine)

    async with app_engine.begin() as conn:
        super_role = await _role(conn, "super_admin")
        other = await _user(conn, "active")
        # Never two (partial unique index).
        await _fails(
            conn,
            "INSERT INTO iam.role_assignments (id, principal_type, principal_id, role_id) VALUES (:id, 'user', :p, :r)",
            UNIQUE_VIOLATION,
            id=uuid7(),
            p=other,
            r=super_role,
        )
        # The flag is derived from the role, never supplied.
        ordinary = uuid7()
        await conn.execute(
            text(
                "INSERT INTO iam.role_assignments (id, principal_type, principal_id, role_id, super_admin) "
                "VALUES (:id, 'user', :p, :r, true)"
            ),
            {"id": ordinary, "p": other, "r": await _role(conn, "user_type_4")},
        )
        flag = (
            await conn.execute(
                text("SELECT super_admin FROM iam.role_assignments WHERE id = :id"), {"id": ordinary}
            )
        ).scalar_one()
        assert flag is False
        # API clients never hold super-admin rights.
        client = uuid7()
        await conn.execute(
            text("INSERT INTO iam.api_clients (id, name, secret_hash) VALUES (:id, 'c', :h)"),
            {"id": client, "h": b"\x00" * 32},
        )
        await _fails(
            conn,
            "INSERT INTO iam.role_assignments (id, principal_type, principal_id, role_id) "
            "VALUES (:id, 'api_client', :p, :r)",
            CHECK_VIOLATION,
            id=uuid7(),
            p=client,
            r=super_role,
        )
        # The holder cannot be suspended or deactivated before a transfer.
        await _fails(conn, "UPDATE iam.users SET status = 'deactivated' WHERE id = :u", INTEGRITY, u=holder)
        await _fails(conn, "UPDATE iam.users SET status = 'suspended' WHERE id = :u", INTEGRITY, u=holder)
        # Assignments refer to real principals.
        await _fails(
            conn,
            "INSERT INTO iam.role_assignments (id, principal_type, principal_id, role_id) VALUES (:id, 'user', :p, :r)",
            FOREIGN_KEY,
            id=uuid7(),
            p=uuid7(),
            r=super_role,
        )
        await conn.rollback()

    # Never zero: revoking the only super admin fails when the transaction commits.
    with pytest.raises(DBAPIError) as caught:
        async with app_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE iam.role_assignments SET revoked_at = now() WHERE super_admin AND revoked_at IS NULL"
                )
            )
    assert sqlstate_of(caught.value) == INTEGRITY
    assert "exactly one super admin" in str(caught.value.orig)

    # A transfer (revoke and grant in one transaction) is fine.
    async with app_engine.begin() as conn:
        successor = await _user(conn, "active")
        await conn.execute(
            text(
                "UPDATE iam.role_assignments SET revoked_at = now() WHERE super_admin AND revoked_at IS NULL"
            )
        )
        await _assign(conn, successor, await _role(conn, "super_admin"))
    async with app_engine.connect() as conn:
        holders = (
            (
                await conn.execute(
                    text(
                        "SELECT principal_id FROM iam.role_assignments WHERE super_admin AND revoked_at IS NULL"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert holders == [successor]


async def test_assignments_are_revoked_never_changed_or_deleted(app_engine: AsyncEngine) -> None:
    await _ensure_super_admin(app_engine)
    async with app_engine.begin() as conn:
        user = await _user(conn)
        assignment = await _assign(conn, user, await _role(conn, "user_type_3"), uuid7())
        await _fails(
            conn,
            "UPDATE iam.role_assignments SET role_id = :r WHERE id = :id",
            INSUFFICIENT_PRIVILEGE,
            r=await _role(conn, "user_type_1"),
            id=assignment,
        )
        await _fails(
            conn,
            "UPDATE iam.role_assignments SET site_id = NULL WHERE id = :id",
            INSUFFICIENT_PRIVILEGE,
            id=assignment,
        )
        await _fails(
            conn, "DELETE FROM iam.role_assignments WHERE id = :id", INSUFFICIENT_PRIVILEGE, id=assignment
        )
        await conn.execute(
            text("UPDATE iam.role_assignments SET revoked_at = now(), revoke_reason = 'test' WHERE id = :id"),
            {"id": assignment},
        )
        await _fails(
            conn,
            "UPDATE iam.role_assignments SET revoked_at = NULL, revoke_reason = NULL WHERE id = :id",
            INSUFFICIENT_PRIVILEGE,
            id=assignment,
        )
        await conn.rollback()


async def test_every_access_change_moves_the_access_version(app_engine: AsyncEngine) -> None:
    """LD-15: caches keyed by the version can never serve a committed change."""
    await _ensure_super_admin(app_engine)

    async def version(conn: AsyncConnection) -> int:
        return (await conn.execute(text("SELECT version FROM iam.access_version"))).scalar_one()

    async with app_engine.begin() as conn:
        start = await version(conn)
        role = uuid7()
        await conn.execute(
            text("INSERT INTO iam.roles (id, code, name, kind) VALUES (:id, :code, 'Temp', 'custom')"),
            {"id": role, "code": f"temp_{role.hex[:8]}"},
        )
        after_role = await version(conn)
        await conn.execute(
            text(
                "INSERT INTO iam.role_permissions (role_id, permission_code) VALUES (:r, 'catalog.item.view')"
            ),
            {"r": role},
        )
        after_grant = await version(conn)
        user = await _user(conn)
        assignment = await _assign(conn, user, role)
        after_assign = await version(conn)
        await conn.execute(
            text("UPDATE iam.role_assignments SET revoked_at = now() WHERE id = :id"), {"id": assignment}
        )
        after_revoke = await version(conn)
        await conn.execute(text("DELETE FROM iam.role_permissions WHERE role_id = :r"), {"r": role})
        after_remove = await version(conn)
        assert start < after_role < after_grant < after_assign < after_revoke < after_remove
        await conn.rollback()
