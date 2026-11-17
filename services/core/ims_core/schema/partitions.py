"""Monthly partitioned tables (AD-68; LLD section 3, "Partitioned tables").

Partitions are created three months ahead and expired ones dropped whole by the database
pipeline using the migration role. A default partition catches late inserts. An outbox
partition still holding a pending event is never dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

MONTHS_AHEAD = 3


@dataclass(frozen=True)
class PartitionedTable:
    schema: str
    table: str
    column: str
    #: Days after which a whole partition may be dropped; None means permanent.
    retention_days: int | None
    #: SQL predicate for rows that pin a partition regardless of age.
    keep_while: str | None = None

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.table}"

    @property
    def default_partition(self) -> str:
        return f"{self.schema}.{self.table}_default"

    def partition_name(self, month: date) -> str:
        return f"{self.table}_y{month.year:04d}m{month.month:02d}"

    def create_default_sql(self) -> str:
        return f"CREATE TABLE {self.default_partition} PARTITION OF {self.qualified} DEFAULT"

    def create_partition_sql(self, month: date) -> str:
        start = month_start(month)
        end = add_months(start, 1)
        return (
            f"CREATE TABLE IF NOT EXISTS {self.schema}.{self.partition_name(start)} "
            f"PARTITION OF {self.qualified} "
            f"FOR VALUES FROM ('{start.isoformat()} 00:00:00+00') TO ('{end.isoformat()} 00:00:00+00')"
        )

    def month_of_partition(self, relname: str) -> date | None:
        match = re.fullmatch(rf"{re.escape(self.table)}_y(\d{{4}})m(\d{{2}})", relname)
        return date(int(match.group(1)), int(match.group(2)), 1) if match else None


#: Every partitioned table in the customer database. Extended as modules add theirs
#: (stock ledger, webhook deliveries, notifications).
PARTITIONED_TABLES: tuple[PartitionedTable, ...] = (
    PartitionedTable("audit", "audit_log", "occurred_at", retention_days=None),
    PartitionedTable(
        "integration", "outbox_events", "occurred_at", retention_days=400, keep_while="status = 'pending'"
    ),
)


def month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def add_months(value: date, months: int) -> date:
    index = value.year * 12 + (value.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def months_to_ensure(today: date, months_ahead: int = MONTHS_AHEAD) -> list[date]:
    """Current month plus the next ``months_ahead`` months."""
    first = month_start(today)
    return [add_months(first, offset) for offset in range(months_ahead + 1)]
