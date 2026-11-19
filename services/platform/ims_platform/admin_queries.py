"""Reads for the Platform Console (LLD 6.8 /platform/v1): customers with their licence, database,
derived licence state and provisioning run; licences; modules; platform audit.

Licence state is derived from the customer status and licence dates at read time, never stored
(LLD 4, 6.4). Nothing here reads a customer database: usage inside a customer (sites and users in
use) is not visible to the platform tier (AD-13).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ims_common.clock import Clock
from ims_contracts.enums import CustomerStatus
from ims_contracts.licence import LicenceState

_CUSTOMERS = """
SELECT c.id, c.code, c.legal_name, c.status, c.gxp_mode, c.gxp_locked, c.placement, c.created_at,
       l.id AS licence_id, l.licence_no, l.record_status, l.valid_from, l.valid_until, l.grace_days,
       l.max_sites, l.max_users,
       COALESCE((SELECT array_agg(m.module_code ORDER BY m.module_code)
                   FROM platform.licence_modules m WHERE m.licence_id = l.id), '{}') AS modules,
       d.database_name, d.cluster_ref, d.status AS database_status, d.schema_version,
       r.id AS run_id, r.status AS run_status, r.current_step AS run_step
  FROM platform.customers c
  LEFT JOIN LATERAL (SELECT * FROM platform.licences x WHERE x.customer_id = c.id
                      ORDER BY (x.record_status = 'active') DESC, x.created_at DESC LIMIT 1) l ON true
  LEFT JOIN platform.customer_databases d ON d.customer_id = c.id
  LEFT JOIN platform.provisioning_runs r ON r.customer_id = c.id
"""


@dataclass(frozen=True)
class LicenceView:
    id: UUID
    licence_no: str
    record_status: str
    valid_from: datetime
    valid_until: datetime
    grace_days: int
    max_sites: int
    max_users: int
    modules: list[str]


@dataclass(frozen=True)
class CustomerView:
    id: UUID
    code: str
    legal_name: str
    status: str
    gxp_mode: bool
    gxp_locked: bool
    placement: str
    created_at: datetime
    licence: LicenceView | None
    licence_state: LicenceState | None
    grace_ends_at: datetime | None
    database: dict[str, Any] | None
    run: dict[str, Any] | None


def derive(status: str, licence: LicenceView | None, now: datetime) -> LicenceState | None:
    """LLD 6.4 state(), for an active licence of a customer past provisioning."""
    if status == CustomerStatus.TERMINATED.value:
        return LicenceState.TERMINATED
    if status == CustomerStatus.SUSPENDED.value:
        return LicenceState.SUSPENDED
    if status == CustomerStatus.PROVISIONING.value or licence is None or licence.record_status != "active":
        return None
    if now < licence.valid_until:
        return LicenceState.ACTIVE
    if now < licence.valid_until + timedelta(days=licence.grace_days):
        return LicenceState.GRACE
    return LicenceState.READ_ONLY


class AdminQueries:
    def __init__(self, engine: AsyncEngine, clock: Clock) -> None:
        self._engine = engine
        self._clock = clock

    def _customer(self, row: Any) -> CustomerView:
        licence = (
            LicenceView(
                id=row["licence_id"],
                licence_no=row["licence_no"],
                record_status=row["record_status"],
                valid_from=row["valid_from"],
                valid_until=row["valid_until"],
                grace_days=row["grace_days"],
                max_sites=row["max_sites"],
                max_users=row["max_users"],
                modules=list(row["modules"]),
            )
            if row["licence_id"] is not None
            else None
        )
        state = derive(row["status"], licence, self._clock.now())
        return CustomerView(
            id=row["id"],
            code=row["code"],
            legal_name=row["legal_name"],
            status=row["status"],
            gxp_mode=row["gxp_mode"],
            gxp_locked=row["gxp_locked"],
            placement=row["placement"],
            created_at=row["created_at"],
            licence=licence,
            licence_state=state,
            grace_ends_at=licence.valid_until + timedelta(days=licence.grace_days)
            if state is LicenceState.GRACE and licence
            else None,
            database=(
                {
                    "database_name": row["database_name"],
                    "cluster_ref": row["cluster_ref"],
                    "status": row["database_status"],
                    "schema_version": row["schema_version"],
                }
                if row["database_name"] is not None
                else None
            ),
            run=(
                {"id": row["run_id"], "status": row["run_status"], "current_step": row["run_step"]}
                if row["run_id"] is not None
                else None
            ),
        )

    async def customers(self) -> list[CustomerView]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(text(_CUSTOMERS + " ORDER BY c.code"))).mappings().all()
        return [self._customer(row) for row in rows]

    async def customer(self, customer_id: UUID) -> CustomerView | None:
        async with self._engine.connect() as conn:
            row = (
                (await conn.execute(text(_CUSTOMERS + " WHERE c.id = :id"), {"id": customer_id}))
                .mappings()
                .first()
            )
        return self._customer(row) if row else None

    async def licences(self, customer_id: UUID) -> list[LicenceView]:
        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT l.id, l.licence_no, l.record_status, l.valid_from, l.valid_until, "
                        "l.grace_days, "
                        "l.max_sites, l.max_users, COALESCE((SELECT array_agg(m.module_code ORDER BY "
                        "m.module_code) "
                        "FROM platform.licence_modules m WHERE m.licence_id = l.id), '{}') AS modules "
                        "FROM platform.licences l WHERE l.customer_id = :id ORDER BY l.created_at DESC"
                    ),
                    {"id": customer_id},
                )
            ).mappings()
            return [LicenceView(**{**row, "modules": list(row["modules"])}) for row in rows]

    async def licence_customer(self, licence_id: UUID) -> UUID | None:
        async with self._engine.connect() as conn:
            return (
                await conn.execute(
                    text("SELECT customer_id FROM platform.licences WHERE id = :id"), {"id": licence_id}
                )
            ).scalar_one_or_none()

    async def modules(self) -> list[dict[str, Any]]:
        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(text("SELECT code, name, active FROM platform.modules ORDER BY code"))
            ).mappings()
            return [dict(row) for row in rows]

    async def audit(
        self, *, customer_id: UUID | None, before_seq: int | None, limit: int
    ) -> list[dict[str, Any]]:
        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT seq, occurred_at, actor, action, entity_type, entity_id, customer_id, "
                        "before, after, "
                        "reason, request_id FROM platform.platform_audit "
                        "WHERE (CAST(:customer AS uuid) IS NULL OR customer_id = :customer) "
                        "AND (CAST(:before AS bigint) IS NULL OR seq < :before) ORDER BY seq DESC LIMIT "
                        ":limit"
                    ),
                    {"customer": customer_id, "before": before_seq, "limit": limit},
                )
            ).mappings()
            return [dict(row) for row in rows]
