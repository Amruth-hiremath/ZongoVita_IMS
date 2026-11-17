"""Schema migrations (AD-29, LD-85; LLD 6.7).

One database at a time, as that database's migration role, in a single transaction with a short
lock timeout: a failed migration rolls back completely, so the database stays on its previous
version and keeps serving. Staged rollout across customers (canary, 5%, 25%, 100%) and its stop
rule sit on top of ``migrate_customer_database`` and are driven by the Platform Service's
migration-run records.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

import ims_core
import ims_platform
from ims_common.pg import SQLSTATE_LOCK_NOT_AVAILABLE, sqlstate_of
from ims_common.secrets import SecretsStore
from ims_db_pipeline.cluster import ClusterAdmin
from ims_db_pipeline.partitions import PartitionReport, ensure_partitions
from ims_db_pipeline.provision import (
    CONTROL_PLANE_DATABASE,
    PLATFORM_MIGRATION_SECRET_REF,
    CustomerDatabase,
)

MIGRATION_LOCK_TIMEOUT = "3s"  # LLD 6.7
MIGRATION_ATTEMPTS = 5


@dataclass(frozen=True)
class MigrationOutcome:
    database: str
    from_version: str | None
    to_version: str
    partitions: PartitionReport | None = None

    @property
    def changed(self) -> bool:
        return self.from_version != self.to_version


def _alembic_config(script_location: Path, connection: Connection, attributes: dict[str, Any]) -> Config:
    config = Config()
    config.set_main_option("script_location", str(script_location))
    config.attributes["connection"] = connection
    config.attributes.update(attributes)
    return config


def schema_head(script_location: Path) -> str:
    """Head revision of a migration directory."""
    config = Config()
    config.set_main_option("script_location", str(script_location))
    head = ScriptDirectory.from_config(config).get_current_head()
    if head is None:
        raise RuntimeError(f"no migrations found in {script_location}")
    return head


def _upgrade(
    connection: Connection,
    script_location: Path,
    attributes: dict[str, Any],
    after_upgrade: Callable[[Connection], PartitionReport] | None,
) -> tuple[str | None, str, PartitionReport | None]:
    config = _alembic_config(script_location, connection, attributes)
    head = schema_head(script_location)
    current = MigrationContext.configure(connection).get_current_revision()
    if current != head:
        command.upgrade(config, head)
    report = after_upgrade(connection) if after_upgrade else None
    return current, head, report


async def _run(
    cluster: ClusterAdmin,
    *,
    database: str,
    user: str,
    password: str,
    script_location: Path,
    attributes: dict[str, Any],
    after_upgrade: Callable[[Connection], PartitionReport] | None,
) -> MigrationOutcome:
    engine = cluster.engine_as(database, user, password)
    try:
        for attempt in range(1, MIGRATION_ATTEMPTS + 1):
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(f"SET LOCAL lock_timeout = '{MIGRATION_LOCK_TIMEOUT}'"))
                    current, head, report = await conn.run_sync(
                        _upgrade, script_location, attributes, after_upgrade
                    )
                return MigrationOutcome(database, current, head, report)
            except DBAPIError as exc:
                # A busy table: back off and retry rather than queue behind application traffic.
                if sqlstate_of(exc) != SQLSTATE_LOCK_NOT_AVAILABLE or attempt == MIGRATION_ATTEMPTS:
                    raise
                await asyncio.sleep(min(2**attempt, 15) + random.random())  # noqa: S311 - jitter
        raise AssertionError("unreachable")  # pragma: no cover
    finally:
        await engine.dispose()


async def migrate_customer_database(
    cluster: ClusterAdmin,
    secrets: SecretsStore,
    customer_code: str,
    *,
    today: datetime | None = None,
) -> MigrationOutcome:
    """Bring one customer database to the schema head and make sure its partitions exist."""
    target = CustomerDatabase.for_customer(customer_code)
    credential = await secrets.get(target.migration_secret_ref)
    day = (today or datetime.now(UTC)).date()
    return await _run(
        cluster,
        database=target.database_name,
        user=target.migration_role,
        password=credential["password"],
        script_location=ims_core.migrations_path(),
        attributes={"app_role": target.app_role, "breakglass_role": target.breakglass_role},
        after_upgrade=lambda connection: ensure_partitions(connection, day),
    )


async def migrate_control_plane(cluster: ClusterAdmin, secrets: SecretsStore) -> MigrationOutcome:
    credential = await secrets.get(PLATFORM_MIGRATION_SECRET_REF)
    return await _run(
        cluster,
        database=CONTROL_PLANE_DATABASE,
        user=credential["username"],
        password=credential["password"],
        script_location=ims_platform.migrations_path(),
        attributes={},
        after_upgrade=None,
    )
