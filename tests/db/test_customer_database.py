"""Customer database: isolation, least-privilege roles, immutable history, partitions.

Covers the LLD section 17 database rows that apply to the kernel baseline: no hard deletes,
immutable history, tenant isolation at the database layer, pipeline-only migrations, partitions.
Application-role access always goes through the pooler in transaction mode.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

import ims_core
from ims_common.ids import uuid7
from ims_common.pg import SQLSTATE_INSUFFICIENT_PRIVILEGE, sqlstate_of
from ims_common.secrets import SecretAccessDeniedError
from ims_core.schema.access import (
    COLUMN_UPDATES,
    CUSTOMER_SCHEMAS,
    DELETE_EXCEPTION_LIST,
    TABLE_ACCESS,
    TRIGGER_PROTECTED,
    AccessClass,
)
from ims_core.schema.partitions import PARTITIONED_TABLES, add_months, month_start
from ims_core.schema.version import SCHEMA_HEAD, SCHEMA_PREVIOUS, SCHEMA_SUPPORTED
from ims_db_pipeline.migrate import migrate_customer_database, schema_head
from ims_db_pipeline.partitions import drop_expired_partitions, ensure_partitions
from ims_db_pipeline.provision import APP_ROLE_DEFAULTS, provision_customer_database
from tests.support.stack import Customer, Stack

pytestmark = pytest.mark.db

AUDIT_INSERT = text(
    "INSERT INTO audit.audit_log (actor_type, action, entity_type, entity_id, source) "
    "VALUES ('system', :action, 'test', '1', 'system')"
)
OUTBOX_INSERT = text(
    "INSERT INTO integration.outbox_events (id, event_type, subject_type, subject_id, subject_version, payload) "
    "VALUES (:id, 'test.thing.changed', 'thing', '1', 1, '{}')"
)


async def _rejected(engine, sql: str, **params: object) -> str | None:
    with pytest.raises(DBAPIError) as excinfo:
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)
    return sqlstate_of(excinfo.value)


# ----------------------------------------------------------------------------------- isolation
async def test_a_customer_credential_cannot_enter_another_customers_database(
    stack: Stack, customer_a: Customer, customer_b: Customer
) -> None:
    """Isolation layer three (HLD section 8): a separate database with its own credentials."""
    a_secret = await stack.pipeline_secrets.get(customer_a.db.app_secret_ref)
    own = stack.pooled_engine(customer_a.db.database_name, customer_a.db.app_role, a_secret["password"])
    try:
        async with own.connect() as conn:
            row = (await conn.execute(text("SELECT current_database(), current_user"))).one()
            assert tuple(row) == (customer_a.db.database_name, customer_a.db.app_role)
    finally:
        await own.dispose()

    foreign_pooled = stack.pooled_engine(
        customer_b.db.database_name, customer_a.db.app_role, a_secret["password"]
    )
    foreign_direct = stack.cluster.engine_as(
        customer_b.db.database_name, customer_a.db.app_role, a_secret["password"]
    )
    for engine in (foreign_pooled, foreign_direct):
        try:
            with pytest.raises(DBAPIError):
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()

    # There is no cross-database reference to try either: other databases are simply not there.
    engine = await stack.app_engine(customer_a.db)
    try:
        state = await _rejected(engine, f'SELECT * FROM "{customer_b.db.database_name}".config.settings')
        assert state == "0A000"  # cross-database references are not implemented
    finally:
        await engine.dispose()


async def test_each_customer_has_its_own_roles_and_secrets(
    stack: Stack, customer_a: Customer, customer_b: Customer
) -> None:
    a = await stack.pipeline_secrets.get(customer_a.db.app_secret_ref)
    b = await stack.pipeline_secrets.get(customer_b.db.app_secret_ref)
    assert a["username"] != b["username"]
    assert a["password"] != b["password"]
    engine = stack.cluster.admin_engine()
    try:
        async with engine.connect() as conn:
            roles = (
                await conn.execute(
                    text(
                        "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                        "FROM pg_roles WHERE rolname ~ '^ims_(app|mig|breakglass)_(alpha|bravo)$' ORDER BY 1"
                    )
                )
            ).all()
            owners = dict(
                (
                    await conn.execute(
                        text(
                            "SELECT datname, pg_get_userbyid(datdba) FROM pg_database "
                            "WHERE datname IN ('ims_c_alpha', 'ims_c_bravo')"
                        )
                    )
                ).all()
            )
            public_connect = (
                await conn.execute(text("SELECT has_database_privilege('public', 'ims_c_alpha', 'CONNECT')"))
            ).scalar_one()
    finally:
        await engine.dispose()
    assert [r.rolname for r in roles] == [
        "ims_app_alpha",
        "ims_app_bravo",
        "ims_breakglass_alpha",
        "ims_breakglass_bravo",
        "ims_mig_alpha",
        "ims_mig_bravo",
    ]
    assert not any(any(r[1:]) for r in roles), "no customer role has any cluster-level power"
    assert owners == {"ims_c_alpha": "ims_mig_alpha", "ims_c_bravo": "ims_mig_bravo"}
    assert public_connect is False


async def test_per_customer_limits_apply_through_the_pooler(stack: Stack, customer_a: Customer) -> None:
    """LD-08 / AD-84: timeouts are role defaults, so they hold in transaction-pooling mode."""
    engine = await stack.app_engine(customer_a.db)
    try:
        async with engine.connect() as conn:
            settings = {
                name: (await conn.execute(text(f"SHOW {name}"))).scalar_one()
                for name in ("statement_timeout", "lock_timeout", "idle_in_transaction_session_timeout")
            }
            search_path = (await conn.execute(text("SHOW search_path"))).scalar_one()
            application = (await conn.execute(text("SHOW application_name"))).scalar_one()
    finally:
        await engine.dispose()
    assert settings == {k: v for k, v in APP_ROLE_DEFAULTS.items() if k != "search_path"}
    assert search_path == '""', "only schema-qualified names resolve"
    assert application == "ims-tests", "application_name travels as a startup parameter (LD-75)"


async def test_statement_timeout_is_enforced_per_customer(stack: Stack, customer_a: Customer) -> None:
    engine = await stack.app_engine(customer_a.db)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SET LOCAL statement_timeout = '200ms'"))
            with pytest.raises(DBAPIError) as excinfo:
                await conn.execute(text("SELECT pg_sleep(2)"))
            assert sqlstate_of(excinfo.value) == "57014"
    finally:
        await engine.dispose()


async def test_migration_role_cannot_be_used_through_the_pooler(stack: Stack, customer_a: Customer) -> None:
    """Migrations connect directly; the pooler does not even know the migration roles."""
    credential = await stack.pipeline_secrets.get(customer_a.db.migration_secret_ref)
    pooled = stack.pooled_engine(
        customer_a.db.database_name, customer_a.db.migration_role, credential["password"]
    )
    try:
        with pytest.raises(DBAPIError):
            async with pooled.connect() as conn:
                await conn.execute(text("SELECT 1"))
    finally:
        await pooled.dispose()
    direct = await stack.migration_engine(customer_a.db)
    try:
        async with direct.connect() as conn:
            assert (
                await conn.execute(text("SELECT current_user"))
            ).scalar_one() == customer_a.db.migration_role
    finally:
        await direct.dispose()


async def test_core_identity_cannot_read_migration_or_break_glass_credentials(
    stack: Stack, customer_a: Customer
) -> None:
    await stack.core_secrets.get(customer_a.db.app_secret_ref)
    for ref in (customer_a.db.migration_secret_ref, customer_a.db.breakglass_secret_ref):
        with pytest.raises(SecretAccessDeniedError):
            await stack.core_secrets.get(ref)


async def test_break_glass_role_has_no_table_rights(stack: Stack, customer_a: Customer) -> None:
    """LD-84: the role exists from provisioning and can do nothing until its function is granted."""
    credential = await stack.pipeline_secrets.get(customer_a.db.breakglass_secret_ref)
    engine = stack.pooled_engine(
        customer_a.db.database_name, customer_a.db.breakglass_role, credential["password"]
    )
    try:
        for sql in (
            "SELECT * FROM config.settings",
            "SELECT * FROM audit.audit_log",
            "INSERT INTO config.settings (key, value) VALUES ('a.b', '1')",
        ):
            assert await _rejected(engine, sql) == SQLSTATE_INSUFFICIENT_PRIVILEGE
    finally:
        await engine.dispose()


# ------------------------------------------------------------------------------ access classes
async def test_every_table_has_exactly_the_privileges_of_its_access_class(
    stack: Stack, customer_a: Customer
) -> None:
    """The catalogue is compared with the code-side registry, so a table cannot ship with DELETE
    outside the exception list or with UPDATE on history."""
    engine = await stack.migration_engine(customer_a.db)
    try:
        async with engine.connect() as conn:
            tables = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT n.nspname || '.' || c.relname
                          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                         WHERE n.nspname = ANY(:schemas) AND c.relkind IN ('r', 'p') AND NOT c.relispartition
                        """
                        ),
                        {"schemas": list(CUSTOMER_SCHEMAS)},
                    )
                )
                .scalars()
                .all()
            )
            assert set(tables) == set(TABLE_ACCESS), "every table must be classified in schema/access.py"

            for table, access in TABLE_ACCESS.items():
                actual = {
                    privilege
                    for privilege in (
                        "SELECT",
                        "INSERT",
                        "UPDATE",
                        "DELETE",
                        "TRUNCATE",
                        "REFERENCES",
                        "TRIGGER",
                    )
                    if (
                        await conn.execute(
                            text("SELECT has_table_privilege(:role, :table, :privilege)"),
                            {"role": customer_a.db.app_role, "table": table, "privilege": privilege},
                        )
                    ).scalar_one()
                }
                column_level = {
                    privilege
                    for privilege in ("INSERT", "UPDATE")
                    if (
                        await conn.execute(
                            text("SELECT has_any_column_privilege(:role, :table, :privilege)"),
                            {"role": customer_a.db.app_role, "table": table, "privilege": privilege},
                        )
                    ).scalar_one()
                }
                effective = actual | column_level
                expected = set(access.value)
                if table in COLUMN_UPDATES:
                    expected.add("UPDATE")
                    updatable = (
                        (
                            await conn.execute(
                                text(
                                    "SELECT column_name FROM information_schema.column_privileges "
                                    "WHERE grantee = :role AND table_schema || '.' || table_name = :table "
                                    "AND privilege_type = 'UPDATE'"
                                ),
                                {"role": customer_a.db.app_role, "table": table},
                            )
                        )
                        .scalars()
                        .all()
                    )
                    assert set(updatable) == COLUMN_UPDATES[table], table
                assert effective == expected, f"{table}: {effective} != {expected}"
                if access is AccessClass.DELETABLE:
                    assert table in DELETE_EXCEPTION_LIST, f"{table} may not be deletable"

            # Monthly partitions carry no direct grants: access is through the parent only.
            direct = (
                await conn.execute(
                    text(
                        """
                        SELECT count(*) FROM information_schema.role_table_grants g
                          JOIN pg_class c ON c.relname = g.table_name
                         WHERE g.grantee = :role AND c.relispartition
                        """
                    ),
                    {"role": customer_a.db.app_role},
                )
            ).scalar_one()
            assert direct == 0

            for schema in CUSTOMER_SCHEMAS:
                usage, create = (
                    await conn.execute(
                        text(
                            "SELECT has_schema_privilege(:r, :s, 'USAGE'), has_schema_privilege(:r, :s, 'CREATE')"
                        ),
                        {"r": customer_a.db.app_role, "s": schema},
                    )
                ).one()
                assert (usage, create) == (True, False), schema
    finally:
        await engine.dispose()


async def test_application_role_has_no_ddl_and_no_hard_deletes(stack: Stack, customer_a: Customer) -> None:
    engine = await stack.app_engine(customer_a.db)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO config.settings (key, value) VALUES ('db.test', '1') ON CONFLICT DO NOTHING"
                )
            )
        for sql in (
            "CREATE TABLE config.sneaky (id int)",
            "CREATE SCHEMA sneaky",
            "ALTER TABLE config.settings ADD COLUMN x int",
            "DROP TABLE config.settings",
            "CREATE TEMP TABLE scratch (id int)",
            "CREATE FUNCTION config.f() RETURNS int LANGUAGE sql AS 'SELECT 1'",
            "ALTER TABLE audit.audit_log DISABLE TRIGGER audit_log_append_only",
            "TRUNCATE config.settings",
            "DELETE FROM config.settings WHERE key = 'db.test'",  # AD-67: no hard deletes
        ):
            assert await _rejected(engine, sql) == SQLSTATE_INSUFFICIENT_PRIVILEGE, sql
        # SET LOCAL lasts for one transaction only; the role default is back on the next one.
        async with engine.connect() as conn:
            await conn.execute(text("SET LOCAL statement_timeout = '1s'"))
            await conn.commit()
            assert (await conn.execute(text("SHOW statement_timeout"))).scalar_one() == "15s"
    finally:
        await engine.dispose()


@pytest.mark.slow
async def test_pooler_stops_a_runaway_query_even_if_the_role_lifts_its_own_timeout(
    stack: Stack, customer_b: Customer
) -> None:
    """statement_timeout is a role default, and PostgreSQL lets any role override its own
    user-level settings. The pooler's query_timeout is the backstop the role cannot change."""
    engine = await stack.app_engine(customer_b.db)
    started = datetime.now(UTC)
    try:
        with pytest.raises(DBAPIError):
            async with engine.connect() as conn:
                await conn.execute(text("SET LOCAL statement_timeout = 0"))
                await conn.execute(text("SELECT pg_sleep(45)"))
        elapsed = (datetime.now(UTC) - started).total_seconds()
        assert 15 <= elapsed < 40, f"stopped after {elapsed:.0f}s"
        async with engine.connect() as conn:  # the customer is served again straight away
            assert (await conn.execute(text("SELECT 1"))).scalar_one() == 1
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------- immutable history
async def test_audit_log_is_append_only_for_everyone(stack: Stack, customer_a: Customer) -> None:
    app = await stack.app_engine(customer_a.db)
    owner = await stack.migration_engine(customer_a.db)
    try:
        async with app.begin() as conn:
            await conn.execute(AUDIT_INSERT, {"action": "history.test"})
        where = "WHERE action = 'history.test'"
        for sql in (
            f"UPDATE audit.audit_log SET action = 'rewritten' {where}",
            f"DELETE FROM audit.audit_log {where}",
            "TRUNCATE audit.audit_log",
        ):
            assert await _rejected(app, sql) == SQLSTATE_INSUFFICIENT_PRIVILEGE, sql
        # Even the table owner is stopped: the trigger is the second, independent guard (LD-06).
        for sql in (
            f"UPDATE audit.audit_log SET action = 'rewritten' {where}",
            f"DELETE FROM audit.audit_log {where}",
            "TRUNCATE audit.audit_log",
        ):
            assert await _rejected(owner, sql) == SQLSTATE_INSUFFICIENT_PRIVILEGE, sql
        assert {"audit.audit_log"} == TRIGGER_PROTECTED
        async with app.connect() as conn:
            assert (
                await conn.execute(text(f"SELECT count(*) FROM audit.audit_log {where}"))
            ).scalar_one() == 1
    finally:
        await app.dispose()
        await owner.dispose()


async def test_application_cannot_choose_when_or_in_what_order_history_happened(
    stack: Stack, customer_a: Customer
) -> None:
    engine = await stack.app_engine(customer_a.db)
    try:
        base = (
            "INSERT INTO audit.audit_log (actor_type, action, entity_type, entity_id, source, {col}) "
            "VALUES ('system', 'forged', 'test', '1', 'system', {val})"
        )
        for col, val in (
            ("occurred_at", "'2020-01-01 00:00:00+00'"),
            ("seq", "1"),
            ("txid", "'1'::xid8"),
        ):
            assert (
                await _rejected(engine, base.format(col=col, val=val)) == SQLSTATE_INSUFFICIENT_PRIVILEGE
            ), col
        async with engine.begin() as conn:
            await conn.execute(AUDIT_INSERT, {"action": "ordering.one"})
            await conn.execute(AUDIT_INSERT, {"action": "ordering.two"})
            rows = (
                await conn.execute(
                    text(
                        "SELECT seq, txid::text, occurred_at, pg_current_xact_id()::text AS current "
                        "FROM audit.audit_log WHERE action LIKE 'ordering.%' ORDER BY seq"
                    )
                )
            ).all()
        assert rows[1].seq == rows[0].seq + 1
        assert rows[0].txid == rows[1].txid == rows[0].current, (
            "both entries carry the business transaction's ID"
        )
        assert abs((rows[0].occurred_at - datetime.now(UTC)).total_seconds()) < 60
    finally:
        await engine.dispose()


async def test_audit_constraints(stack: Stack, customer_a: Customer) -> None:
    engine = await stack.app_engine(customer_a.db)
    insert = (
        "INSERT INTO audit.audit_log (actor_type, actor_id, action, entity_type, entity_id, source, reason) "
        "VALUES (:t, :a, 'x', 'test', '1', :s, :r)"
    )
    try:
        for params in (
            {"t": "user", "a": None, "s": "ui", "r": None},  # a named actor type needs an actor
            {"t": "robot", "a": None, "s": "ui", "r": None},
            {"t": "system", "a": None, "s": "carrier-pigeon", "r": None},
            {"t": "system", "a": None, "s": "system", "r": "   "},  # a blank reason is not a reason
        ):
            assert await _rejected(engine, insert, **params) == "23514", params
    finally:
        await engine.dispose()


async def test_outbox_events_can_only_be_marked_dispatched(stack: Stack, customer_a: Customer) -> None:
    engine = await stack.app_engine(customer_a.db)
    event_id = uuid7()
    where = "WHERE id = :id"
    try:
        async with engine.begin() as conn:
            await conn.execute(OUTBOX_INSERT, {"id": event_id})
            row = (
                await conn.execute(
                    text(
                        f"SELECT status, seq, txid::text, pg_current_xact_id()::text AS cur FROM integration.outbox_events {where}"
                    ),
                    {"id": event_id},
                )
            ).one()
        assert (row.status, row.txid) == ("pending", row.cur)

        for sql in (
            f"UPDATE integration.outbox_events SET payload = '{{\"forged\": true}}' {where}",
            f"UPDATE integration.outbox_events SET event_type = 'other.thing.happened' {where}",
            f"UPDATE integration.outbox_events SET seq = 1 {where}",
            f"DELETE FROM integration.outbox_events {where}",
            "TRUNCATE integration.outbox_events",
        ):
            assert await _rejected(engine, sql, id=event_id) == SQLSTATE_INSUFFICIENT_PRIVILEGE, sql
        # Status and dispatch time move together.
        assert (
            await _rejected(
                engine, f"UPDATE integration.outbox_events SET status = 'dispatched' {where}", id=event_id
            )
            == "23514"
        )

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"UPDATE integration.outbox_events SET status = 'dispatched', dispatched_at = now() {where}"
                ),
                {"id": event_id},
            )
        # A dispatched event is never reopened.
        assert (
            await _rejected(
                engine,
                f"UPDATE integration.outbox_events SET status = 'pending', dispatched_at = NULL {where}",
                id=event_id,
            )
            == SQLSTATE_INSUFFICIENT_PRIVILEGE
        )
        for forged in ("occurred_at", "seq", "txid", "status"):
            sql = (
                f"INSERT INTO integration.outbox_events (id, event_type, subject_type, subject_id, "
                f"subject_version, payload, {forged}) VALUES (:id, 'a.b', 't', '1', 1, '{{}}', DEFAULT)"
            )
            assert await _rejected(engine, sql, id=uuid7()) == SQLSTATE_INSUFFICIENT_PRIVILEGE, forged
    finally:
        await engine.dispose()


async def test_only_expired_idempotency_keys_can_be_deleted(stack: Stack, customer_a: Customer) -> None:
    engine = await stack.app_engine(customer_a.db)
    principal = uuid7()
    insert = text(
        "INSERT INTO integration.idempotency_keys (principal_id, key, endpoint, request_hash, expires_at) "
        "VALUES (:p, :k, 'POST /x', decode(repeat('ab', 32), 'hex'), now() + make_interval(hours => :h))"
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(insert, {"p": principal, "k": "live-key-1", "h": 72})
            await conn.execute(insert, {"p": principal, "k": "old-key-01", "h": -1})
        assert (
            await _rejected(
                engine, "DELETE FROM integration.idempotency_keys WHERE principal_id = :p", p=principal
            )
            == SQLSTATE_INSUFFICIENT_PRIVILEGE
        )
        async with engine.begin() as conn:
            deleted = await conn.execute(
                text(
                    "DELETE FROM integration.idempotency_keys WHERE principal_id = :p AND expires_at <= now()"
                ),
                {"p": principal},
            )
            assert deleted.rowcount == 1
            left = (
                (
                    await conn.execute(
                        text("SELECT key FROM integration.idempotency_keys WHERE principal_id = :p"),
                        {"p": principal},
                    )
                )
                .scalars()
                .all()
            )
        assert left == ["live-key-1"]
    finally:
        await engine.dispose()


# -------------------------------------------------------------------- migrations and partitions
def test_application_schema_version_matches_the_migrations() -> None:
    assert schema_head(ims_core.migrations_path()) == SCHEMA_HEAD
    assert {v for v in (SCHEMA_HEAD, SCHEMA_PREVIOUS) if v} == SCHEMA_SUPPORTED
    assert len(SCHEMA_SUPPORTED) <= 2, "skew never exceeds one version (AD-29)"


async def test_provisioning_and_migration_are_safe_to_repeat(stack: Stack, customer_b: Customer) -> None:
    """A failed onboarding run resumes from its step without touching anything (AD-28)."""
    before = await stack.pipeline_secrets.get(customer_b.db.app_secret_ref)
    again = await provision_customer_database(stack.cluster, stack.pipeline_secrets, customer_b.code)
    assert again == customer_b.db
    assert await stack.pipeline_secrets.get(customer_b.db.app_secret_ref) == before, "credential not rotated"
    outcome = await migrate_customer_database(stack.cluster, stack.pipeline_secrets, customer_b.code)
    assert (outcome.from_version, outcome.to_version, outcome.changed) == (SCHEMA_HEAD, SCHEMA_HEAD, False)
    assert outcome.partitions is not None
    assert outcome.partitions.created == []
    engine = await stack.app_engine(customer_b.db)
    try:
        async with engine.connect() as conn:
            assert (await conn.execute(text("SELECT 1"))).scalar_one() == 1
    finally:
        await engine.dispose()


async def test_partitions_exist_three_months_ahead_and_rows_land_in_them(
    stack: Stack, customer_a: Customer
) -> None:
    today = datetime.now(UTC).date()
    expected_months = [add_months(month_start(today), offset) for offset in range(4)]
    owner = await stack.migration_engine(customer_a.db)
    app = await stack.app_engine(customer_a.db)
    try:
        async with owner.connect() as conn:
            for table in PARTITIONED_TABLES:
                names = (
                    (
                        await conn.execute(
                            text(
                                "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid "
                                "JOIN pg_class p ON p.oid = i.inhparent JOIN pg_namespace n ON n.oid = p.relnamespace "
                                "WHERE n.nspname = :s AND p.relname = :t"
                            ),
                            {"s": table.schema, "t": table.table},
                        )
                    )
                    .scalars()
                    .all()
                )
                assert set(names) >= {table.partition_name(m) for m in expected_months}, table.qualified
                assert f"{table.table}_default" in names, "a default partition catches late inserts"
        async with app.begin() as conn:
            await conn.execute(AUDIT_INSERT, {"action": "partition.test"})
            landed = (
                await conn.execute(
                    text(
                        "SELECT tableoid::regclass::text FROM audit.audit_log WHERE action = 'partition.test'"
                    )
                )
            ).scalar_one()
        audit = PARTITIONED_TABLES[0]
        assert landed == f"audit.{audit.partition_name(today)}"
    finally:
        await owner.dispose()
        await app.dispose()


async def test_partition_maintenance_creates_ahead_and_drops_only_what_is_safe(
    stack: Stack, customer_b: Customer
) -> None:
    owner = await stack.migration_engine(customer_b.db)
    outbox = next(t for t in PARTITIONED_TABLES if t.table == "outbox_events")
    audit = next(t for t in PARTITIONED_TABLES if t.table == "audit_log")
    old_done, old_pending, old_audit = date(2024, 1, 1), date(2024, 2, 1), date(2024, 1, 1)
    now = datetime.now(UTC)
    try:
        async with owner.begin() as conn:
            # Simulate history: two outbox months and one audit month from long ago.
            for table, month in ((outbox, old_done), (outbox, old_pending), (audit, old_audit)):
                await conn.execute(text(table.create_partition_sql(month)))
            await conn.execute(
                text(
                    "INSERT INTO integration.outbox_events "
                    "(occurred_at, id, event_type, subject_type, subject_id, subject_version, payload, status, dispatched_at) "
                    "VALUES ('2024-01-15+00', :a, 'a.b', 't', '1', 1, '{}', 'dispatched', '2024-01-15+00'), "
                    "       ('2024-02-15+00', :b, 'a.b', 't', '1', 2, '{}', 'pending', NULL)"
                ),
                {"a": uuid7(), "b": uuid7()},
            )
            await conn.execute(
                text(
                    "INSERT INTO audit.audit_log (occurred_at, actor_type, action, entity_type, entity_id, source) "
                    "VALUES ('2024-01-15+00', 'system', 'ancient', 'test', '1', 'system')"
                )
            )

        async with owner.begin() as conn:
            report = await conn.run_sync(drop_expired_partitions, now)
        assert report.dropped == [f"integration.{outbox.partition_name(old_done)}"]
        assert report.retained == [f"integration.{outbox.partition_name(old_pending)}"], (
            "a partition still holding a pending event is never dropped"
        )
        async with owner.connect() as conn:
            assert (
                await conn.execute(text("SELECT count(*) FROM audit.audit_log WHERE action = 'ancient'"))
            ).scalar_one() == 1, "audit is permanent"
            assert (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM integration.outbox_events WHERE status = 'pending' "
                        "AND occurred_at < '2025-01-01+00'"
                    )
                )
            ).scalar_one() == 1

        # Running ahead of time: a later date needs later partitions, and re-running adds nothing.
        future = add_months(month_start(now.date()), 2)
        async with owner.begin() as conn:
            first = await conn.run_sync(ensure_partitions, future)
            second = await conn.run_sync(ensure_partitions, future)
        assert len(first.created) == 2 * 2, "two more months for each partitioned table"
        assert second.created == []
        assert first.default_rows == {}

        # Not yet expired: a partition inside the 400-day window stays.
        recent = add_months(month_start(now.date()), -3)
        async with owner.begin() as conn:
            await conn.execute(text(outbox.create_partition_sql(recent)))
            again = await conn.run_sync(drop_expired_partitions, now)
        assert again.dropped == []
        assert (now.date() - add_months(recent, 1)) < timedelta(days=400)
    finally:
        await owner.dispose()
