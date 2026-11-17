"""Partition maintenance for monthly partitioned tables (AD-68; LLD section 3).

Runs with the migration role: right after every migration and as the monthly pipeline job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Connection, text

from ims_core.schema.partitions import (
    MONTHS_AHEAD,
    PARTITIONED_TABLES,
    PartitionedTable,
    add_months,
    months_to_ensure,
)


@dataclass
class PartitionReport:
    created: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    #: Expired partitions kept because they still hold rows that must not be lost.
    retained: list[str] = field(default_factory=list)
    #: Tables whose default partition holds rows (an insert arrived for a month with no partition).
    default_rows: dict[str, int] = field(default_factory=dict)


def _existing_partitions(conn: Connection, table: PartitionedTable) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT child.relname
              FROM pg_catalog.pg_inherits i
              JOIN pg_catalog.pg_class parent ON parent.oid = i.inhparent
              JOIN pg_catalog.pg_namespace ns ON ns.oid = parent.relnamespace
              JOIN pg_catalog.pg_class child ON child.oid = i.inhrelid
             WHERE ns.nspname = :schema AND parent.relname = :table
            """
        ),
        {"schema": table.schema, "table": table.table},
    )
    return [row[0] for row in rows]


def ensure_partitions(
    conn: Connection,
    today: date,
    *,
    months_ahead: int = MONTHS_AHEAD,
    tables: tuple[PartitionedTable, ...] = PARTITIONED_TABLES,
) -> PartitionReport:
    """Create the current month's partition and the next ``months_ahead`` months'."""
    report = PartitionReport()
    for table in tables:
        existing = set(_existing_partitions(conn, table))
        for month in months_to_ensure(today, months_ahead):
            name = table.partition_name(month)
            if name not in existing:
                conn.execute(text(table.create_partition_sql(month)))
                report.created.append(f"{table.schema}.{name}")
        stray = conn.execute(text(f"SELECT count(*) FROM {table.default_partition}")).scalar_one()
        if stray:
            report.default_rows[table.qualified] = int(stray)
    return report


def drop_expired_partitions(
    conn: Connection,
    now: datetime,
    *,
    tables: tuple[PartitionedTable, ...] = PARTITIONED_TABLES,
) -> PartitionReport:
    """Drop whole partitions that are past their table's retention.

    A partition is expired when its entire month lies before ``now - retention``. Permanent
    tables (audit, ledger) are never touched, and a partition still holding protected rows
    (for example a pending outbox event) is retained and reported.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    report = PartitionReport()
    for table in tables:
        if table.retention_days is None:
            continue
        cutoff = (now.astimezone(UTC) - timedelta(days=table.retention_days)).date()
        for name in sorted(_existing_partitions(conn, table)):
            month = table.month_of_partition(name)
            if month is None or add_months(month, 1) > cutoff:
                continue
            qualified = f"{table.schema}.{name}"
            if table.keep_while is not None:
                pinned = conn.execute(
                    text(f"SELECT EXISTS (SELECT 1 FROM {qualified} WHERE {table.keep_while})")
                ).scalar_one()
                if pinned:
                    report.retained.append(qualified)
                    continue
            conn.execute(text(f"DROP TABLE {qualified}"))
            report.dropped.append(qualified)
    return report
