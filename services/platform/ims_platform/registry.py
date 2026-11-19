"""Licence Registry: customers, licences, entitlements, database locations (LLD section 4).

Every command is one Control-Plane transaction that makes the change, writes the platform audit
entry and appends to the change feed, so a change that products must react to can never commit
without its notice. Commands that touch one customer lock that customer's row first, which
serialises them per customer and keeps lock order consistent.

Licence state (Active, Grace, Read-only, Suspended, Terminated; AD-78) is not stored. It is
derived from the customer status and licence dates wherever a snapshot is evaluated
(``ims_contracts.licence.derive_state``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ims_common.clock import Clock, SystemClock
from ims_common.ids import uuid7
from ims_common.pg import SQLSTATE_UNIQUE_VIOLATION, sqlstate_of
from ims_common.problem import DomainError
from ims_contracts.enums import ChangeType, CustomerStatus, DatabaseStatus, Placement
from ims_contracts.errors import ErrorCode, FieldError
from ims_contracts.licence import DatabaseLocation, LicenceSnapshot
from ims_contracts.platform_api import ChangeFeedEntry, ChangesResponse, DirectoryBundleEntry

#: The newest licence (draft during provisioning), the ready database, and a run that is at the
#: super-admin step right now.
_PROVISIONING_SNAPSHOT_SQL = """
SELECT c.id AS customer_id, c.code AS customer_code, c.status AS customer_status,
       l.valid_from, l.valid_until, l.grace_days, l.max_sites, l.max_users,
       c.gxp_mode, c.gxp_locked, c.placement,
       d.cluster_ref, d.pooler_endpoint, d.database_name, d.app_role, d.secret_ref,
       d.schema_version, d.status AS database_status,
       COALESCE((SELECT array_agg(m.module_code ORDER BY m.module_code)
                   FROM platform.licence_modules m WHERE m.licence_id = l.id), '{}') AS modules,
       (SELECT COALESCE(max(f.seq), 0) FROM platform.change_feed f) AS feed_seq
  FROM platform.customers c
  JOIN LATERAL (SELECT * FROM platform.licences x WHERE x.customer_id = c.id
                 ORDER BY x.created_at DESC LIMIT 1) l ON true
  JOIN platform.customer_databases d ON d.customer_id = c.id
  JOIN platform.provisioning_runs r ON r.customer_id = c.id
 WHERE c.id = :id AND c.status = 'provisioning' AND d.status = 'ready'
   AND r.current_step = 'initial_users' AND r.status = 'running'
"""

MAX_CHANGES_PAGE = 500


@dataclass(frozen=True)
class Actor:
    """Who performs a registry command, for the platform audit."""

    ref: str  # e.g. "platform_user:<uuid>", "system:provisioning", "service:ims-worker"
    request_id: str | None = None


_SNAPSHOT_SQL = """
SELECT c.id AS customer_id, c.code AS customer_code, c.status AS customer_status,
       l.valid_from, l.valid_until, l.grace_days, l.max_sites, l.max_users,
       c.gxp_mode, c.gxp_locked, c.placement,
       d.cluster_ref, d.pooler_endpoint, d.database_name, d.app_role, d.secret_ref,
       d.schema_version, d.status AS database_status,
       COALESCE((SELECT array_agg(m.module_code ORDER BY m.module_code)
                   FROM platform.licence_modules m WHERE m.licence_id = l.id), '{}') AS modules,
       -- Same statement, same MVCC snapshot: the data above reflects every change up to feed_seq.
       (SELECT COALESCE(max(f.seq), 0) FROM platform.change_feed f) AS feed_seq
  FROM platform.customers c
  JOIN platform.licences l ON l.customer_id = c.id AND l.record_status = 'active'
  JOIN platform.customer_databases d ON d.customer_id = c.id
 WHERE c.status <> 'provisioning'
"""


def _invalid(field: str, message: str) -> DomainError:
    return DomainError(ErrorCode.VALIDATION_FAILED, errors=[FieldError(field=field, message=message)])


async def audit_change(
    conn: AsyncConnection,
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: UUID | str,
    customer_id: UUID | None,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO platform.platform_audit
                (actor, action, entity_type, entity_id, customer_id, before, after, reason, request_id)
            VALUES (:actor, :action, :entity_type, :entity_id, :customer_id,
                    CAST(:before AS jsonb), CAST(:after AS jsonb), :reason, :request_id)
            """
        ),
        {
            "actor": actor.ref,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "customer_id": customer_id,
            "before": json.dumps(before, default=str) if before is not None else None,
            "after": json.dumps(after, default=str) if after is not None else None,
            "reason": reason,
            "request_id": actor.request_id,
        },
    )


async def notify_change(conn: AsyncConnection, customer_id: UUID, change_type: ChangeType) -> int:
    """Append to the change feed. Call last in the transaction: the feed lock is held until commit."""
    result = await conn.execute(
        text(
            "INSERT INTO platform.change_feed (customer_id, change_type) "
            "VALUES (:customer_id, :change_type) RETURNING seq"
        ),
        {"customer_id": customer_id, "change_type": change_type.value},
    )
    return int(result.scalar_one())


class RegistryService:
    def __init__(self, engine: AsyncEngine, clock: Clock | None = None) -> None:
        self._engine = engine
        self._clock = clock or SystemClock()

    # ------------------------------------------------------------------------------ helpers
    @staticmethod
    async def _lock_customer(conn: AsyncConnection, customer_id: UUID) -> dict[str, Any]:
        row = (
            (
                await conn.execute(
                    text(
                        "SELECT id, code, status, gxp_mode, gxp_locked, placement, version "
                        "FROM platform.customers WHERE id = :id FOR UPDATE"
                    ),
                    {"id": customer_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise DomainError(ErrorCode.NOT_FOUND, "customer not found")
        return dict(row)

    # ----------------------------------------------------------------------------- customers
    async def register_customer(
        self,
        *,
        code: str,
        legal_name: str,
        actor: Actor,
        gxp_mode: bool = False,
        placement: Placement = Placement.SHARED,
    ) -> UUID:
        """Step 1 of provisioning: the customer exists but is not licensed or reachable yet."""
        if gxp_mode and placement is not Placement.DEDICATED:
            raise _invalid("placement", "GxP customers are placed on a dedicated instance")
        customer_id = uuid7()
        try:
            async with self._engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        INSERT INTO platform.customers
                            (id, code, legal_name, gxp_mode, placement, created_by, updated_by)
                        VALUES (:id, :code, :legal_name, :gxp_mode, :placement, :actor, :actor)
                        """
                    ),
                    {
                        "id": customer_id,
                        "code": code,
                        "legal_name": legal_name,
                        "gxp_mode": gxp_mode,
                        "placement": placement.value,
                        "actor": actor.ref,
                    },
                )
                await audit_change(
                    conn,
                    actor,
                    "customer.registered",
                    "customer",
                    customer_id,
                    customer_id,
                    after={
                        "code": code,
                        "legal_name": legal_name,
                        "status": CustomerStatus.PROVISIONING.value,
                        "gxp_mode": gxp_mode,
                        "placement": placement.value,
                    },
                )
        except IntegrityError as exc:
            if sqlstate_of(exc) == SQLSTATE_UNIQUE_VIOLATION:
                raise _invalid("code", "customer code is already in use") from exc
            raise _invalid("code", "customer code or name is not valid") from exc
        return customer_id

    async def _set_status(
        self,
        customer_id: UUID,
        *,
        allowed_from: frozenset[CustomerStatus],
        target: CustomerStatus,
        action: str,
        actor: Actor,
        reason: str | None,
    ) -> None:
        async with self._engine.begin() as conn:
            customer = await self._lock_customer(conn, customer_id)
            current = CustomerStatus(customer["status"])
            if current not in allowed_from:
                raise DomainError(
                    ErrorCode.INVALID_STATE_TRANSITION,
                    f"customer is {current.value}; cannot become {target.value}",
                )
            if target is CustomerStatus.ACTIVE and current is CustomerStatus.PROVISIONING:
                await self._require_ready_for_activation(conn, customer_id)
            await conn.execute(
                text(
                    "UPDATE platform.customers SET status = :status, updated_at = now(), "
                    "updated_by = :actor, version = version + 1 WHERE id = :id"
                ),
                {"status": target.value, "actor": actor.ref, "id": customer_id},
            )
            await audit_change(
                conn,
                actor,
                action,
                "customer",
                customer_id,
                customer_id,
                before={"status": current.value},
                after={"status": target.value},
                reason=reason,
            )
            await notify_change(conn, customer_id, ChangeType.STATUS)

    @staticmethod
    async def _require_ready_for_activation(conn: AsyncConnection, customer_id: UUID) -> None:
        row = (
            (
                await conn.execute(
                    text(
                        """
                    SELECT (SELECT count(*) FROM platform.licences l
                             WHERE l.customer_id = :id AND l.record_status = 'active') AS active_licences,
                           (SELECT d.status FROM platform.customer_databases d
                             WHERE d.customer_id = :id) AS database_status,
                           (SELECT d.schema_version FROM platform.customer_databases d
                             WHERE d.customer_id = :id) AS schema_version
                    """
                    ),
                    {"id": customer_id},
                )
            )
            .mappings()
            .one()
        )
        if row["active_licences"] != 1:
            raise DomainError(ErrorCode.INVALID_STATE_TRANSITION, "customer has no active licence")
        if row["database_status"] != DatabaseStatus.READY.value or row["schema_version"] is None:
            raise DomainError(ErrorCode.INVALID_STATE_TRANSITION, "customer database is not ready")

    async def activate_customer(self, customer_id: UUID, *, actor: Actor) -> None:
        """Last step of provisioning: needs an active licence and a migrated, ready database."""
        await self._set_status(
            customer_id,
            allowed_from=frozenset({CustomerStatus.PROVISIONING}),
            target=CustomerStatus.ACTIVE,
            action="customer.activated",
            actor=actor,
            reason=None,
        )

    async def suspend_customer(self, customer_id: UUID, *, actor: Actor, reason: str) -> None:
        if not reason.strip():
            raise _invalid("reason", "a reason is required to suspend a customer")
        await self._set_status(
            customer_id,
            allowed_from=frozenset({CustomerStatus.ACTIVE}),
            target=CustomerStatus.SUSPENDED,
            action="customer.suspended",
            actor=actor,
            reason=reason,
        )

    async def reinstate_customer(self, customer_id: UUID, *, actor: Actor, reason: str) -> None:
        if not reason.strip():
            raise _invalid("reason", "a reason is required to reinstate a customer")
        await self._set_status(
            customer_id,
            allowed_from=frozenset({CustomerStatus.SUSPENDED}),
            target=CustomerStatus.ACTIVE,
            action="customer.reinstated",
            actor=actor,
            reason=reason,
        )

    async def terminate_customer(self, customer_id: UUID, *, actor: Actor, reason: str) -> None:
        if not reason.strip():
            raise _invalid("reason", "a reason is required to terminate a customer")
        await self._set_status(
            customer_id,
            allowed_from=frozenset({CustomerStatus.ACTIVE, CustomerStatus.SUSPENDED}),
            target=CustomerStatus.TERMINATED,
            action="customer.terminated",
            actor=actor,
            reason=reason,
        )

    async def mark_gxp_locked(self, customer_id: UUID, *, actor: Actor) -> bool:
        """Record that GxP data exists; from then on GxP mode can never be switched off (AD-81).

        Idempotent: returns False if the lock was already set.
        """
        async with self._engine.begin() as conn:
            customer = await self._lock_customer(conn, customer_id)
            if not customer["gxp_mode"]:
                raise DomainError(ErrorCode.INVALID_STATE_TRANSITION, "customer is not in GxP mode")
            if customer["gxp_locked"]:
                return False
            await conn.execute(
                text(
                    "UPDATE platform.customers SET gxp_locked = true, updated_at = now(), "
                    "updated_by = :actor, version = version + 1 WHERE id = :id"
                ),
                {"actor": actor.ref, "id": customer_id},
            )
            await audit_change(
                conn,
                actor,
                "customer.gxp_locked",
                "customer",
                customer_id,
                customer_id,
                before={"gxp_locked": False},
                after={"gxp_locked": True},
            )
            await notify_change(conn, customer_id, ChangeType.GXP)
            return True

    # ------------------------------------------------------------------------------ licences
    async def create_licence(
        self,
        *,
        customer_id: UUID,
        licence_no: str,
        valid_from: datetime,
        valid_until: datetime,
        max_sites: int,
        max_users: int,
        modules: frozenset[str],
        actor: Actor,
        grace_days: int = 14,
    ) -> UUID:
        """Create a draft licence. It has no effect until activated."""
        if valid_from.tzinfo is None or valid_until.tzinfo is None:
            raise _invalid("valid_until", "licence dates must carry a time zone")
        if valid_until <= valid_from:
            raise _invalid("valid_until", "must be after valid_from")
        if not modules:
            raise _invalid("modules", "a licence must include at least one module")
        licence_id = uuid7()
        try:
            async with self._engine.begin() as conn:
                await self._lock_customer(conn, customer_id)
                known = set(
                    (
                        await conn.execute(
                            text("SELECT code FROM platform.modules WHERE active AND code = ANY(:codes)"),
                            {"codes": sorted(modules)},
                        )
                    ).scalars()
                )
                unknown = sorted(modules - known)
                if unknown:
                    raise _invalid("modules", f"unknown or inactive module: {', '.join(unknown)}")
                await conn.execute(
                    text(
                        """
                        INSERT INTO platform.licences
                            (id, customer_id, licence_no, valid_from, valid_until, grace_days,
                             max_sites, max_users, created_by, updated_by)
                        VALUES (:id, :customer_id, :licence_no, :valid_from, :valid_until, :grace_days,
                                :max_sites, :max_users, :actor, :actor)
                        """
                    ),
                    {
                        "id": licence_id,
                        "customer_id": customer_id,
                        "licence_no": licence_no,
                        "valid_from": valid_from,
                        "valid_until": valid_until,
                        "grace_days": grace_days,
                        "max_sites": max_sites,
                        "max_users": max_users,
                        "actor": actor.ref,
                    },
                )
                await conn.execute(
                    text("INSERT INTO platform.licence_modules (licence_id, module_code) VALUES (:l, :m)"),
                    [{"l": licence_id, "m": module} for module in sorted(modules)],
                )
                await audit_change(
                    conn,
                    actor,
                    "licence.created",
                    "licence",
                    licence_id,
                    customer_id,
                    after={
                        "licence_no": licence_no,
                        "valid_from": valid_from,
                        "valid_until": valid_until,
                        "grace_days": grace_days,
                        "max_sites": max_sites,
                        "max_users": max_users,
                        "modules": sorted(modules),
                    },
                )
        except IntegrityError as exc:
            if sqlstate_of(exc) == SQLSTATE_UNIQUE_VIOLATION:
                raise _invalid("licence_no", "licence number is already in use") from exc
            raise _invalid("licence", "licence terms are not valid") from exc
        return licence_id

    async def activate_licence(self, licence_id: UUID, *, actor: Actor) -> None:
        """Make a draft licence the customer's licence; the previous one is superseded.

        This is also how a licence is renewed: a customer in Grace or Read-only returns to Active
        as soon as products pick up the new validity dates.
        """
        async with self._engine.begin() as conn:
            owner = (
                await conn.execute(
                    text("SELECT customer_id FROM platform.licences WHERE id = :id"), {"id": licence_id}
                )
            ).scalar_one_or_none()
            if owner is None:
                raise DomainError(ErrorCode.NOT_FOUND, "licence not found")
            await self._lock_customer(conn, owner)
            status = (
                await conn.execute(
                    text("SELECT record_status FROM platform.licences WHERE id = :id FOR UPDATE"),
                    {"id": licence_id},
                )
            ).scalar_one()
            if status != "draft":
                raise DomainError(ErrorCode.INVALID_STATE_TRANSITION, f"licence is {status}, not draft")
            superseded = (
                await conn.execute(
                    text(
                        "UPDATE platform.licences SET record_status = 'superseded', updated_at = now(), "
                        "updated_by = :actor, version = version + 1 "
                        "WHERE customer_id = :customer_id AND record_status = 'active' RETURNING id"
                    ),
                    {"actor": actor.ref, "customer_id": owner},
                )
            ).scalar_one_or_none()
            await conn.execute(
                text(
                    "UPDATE platform.licences SET record_status = 'active', updated_at = now(), "
                    "updated_by = :actor, version = version + 1 WHERE id = :id"
                ),
                {"actor": actor.ref, "id": licence_id},
            )
            await audit_change(
                conn,
                actor,
                "licence.activated",
                "licence",
                licence_id,
                owner,
                before={"record_status": "draft"},
                after={"record_status": "active", "supersedes": superseded},
            )
            await notify_change(conn, owner, ChangeType.LICENCE)

    # ------------------------------------------------------------------- customer databases
    async def register_database(
        self,
        *,
        customer_id: UUID,
        cluster_ref: str,
        pooler_endpoint: str,
        database_name: str,
        app_role: str,
        secret_ref: str,
        actor: Actor,
        key_ref: str | None = None,
    ) -> UUID:
        """Record where the customer's database will live. Only a secret reference is stored."""
        database_id = uuid7()
        try:
            async with self._engine.begin() as conn:
                await self._lock_customer(conn, customer_id)
                await conn.execute(
                    text(
                        """
                        INSERT INTO platform.customer_databases
                            (id, customer_id, cluster_ref, pooler_endpoint, database_name, app_role,
                             secret_ref, key_ref, created_by, updated_by)
                        VALUES (:id, :customer_id, :cluster_ref, :pooler_endpoint, :database_name,
                                :app_role, :secret_ref, :key_ref, :actor, :actor)
                        """
                    ),
                    {
                        "id": database_id,
                        "customer_id": customer_id,
                        "cluster_ref": cluster_ref,
                        "pooler_endpoint": pooler_endpoint,
                        "database_name": database_name,
                        "app_role": app_role,
                        "secret_ref": secret_ref,
                        "key_ref": key_ref,
                        "actor": actor.ref,
                    },
                )
                await audit_change(
                    conn,
                    actor,
                    "database.registered",
                    "customer_database",
                    database_id,
                    customer_id,
                    after={
                        "cluster_ref": cluster_ref,
                        "pooler_endpoint": pooler_endpoint,
                        "database_name": database_name,
                        "app_role": app_role,
                        "secret_ref": secret_ref,
                        "key_ref": key_ref,
                        "status": DatabaseStatus.CREATING.value,
                    },
                )
        except IntegrityError as exc:
            if sqlstate_of(exc) == SQLSTATE_UNIQUE_VIOLATION:
                raise _invalid(
                    "database_name", "customer already has a database, or the name is taken"
                ) from exc
            raise _invalid("pooler_endpoint", "database location is not valid") from exc
        return database_id

    async def record_database_state(
        self,
        customer_id: UUID,
        *,
        actor: Actor,
        status: DatabaseStatus | None = None,
        schema_version: str | None = None,
    ) -> None:
        """Record the outcome of pipeline work (created, migrating, migrated). The Platform Service
        only records; it never runs DDL itself (AD-13)."""
        if status is None and schema_version is None:
            raise _invalid("status", "nothing to record")
        async with self._engine.begin() as conn:
            await self._lock_customer(conn, customer_id)
            before = (
                (
                    await conn.execute(
                        text(
                            "SELECT id, status, schema_version FROM platform.customer_databases "
                            "WHERE customer_id = :id FOR UPDATE"
                        ),
                        {"id": customer_id},
                    )
                )
                .mappings()
                .first()
            )
            if before is None:
                raise DomainError(ErrorCode.NOT_FOUND, "customer database not registered")
            new_status = status.value if status else before["status"]
            new_version = schema_version if schema_version is not None else before["schema_version"]
            if new_status == before["status"] and new_version == before["schema_version"]:
                return
            await conn.execute(
                text(
                    "UPDATE platform.customer_databases SET status = :status, schema_version = :version, "
                    "updated_at = now(), updated_by = :actor, version = version + 1 WHERE id = :id"
                ),
                {"status": new_status, "version": new_version, "actor": actor.ref, "id": before["id"]},
            )
            await audit_change(
                conn,
                actor,
                "database.state_recorded",
                "customer_database",
                before["id"],
                customer_id,
                before={"status": before["status"], "schema_version": before["schema_version"]},
                after={"status": new_status, "schema_version": new_version},
            )
            await notify_change(conn, customer_id, ChangeType.DATABASE)

    # --------------------------------------------------------------- narrow read interface
    def _to_snapshot(self, row: Any, fetched_at: datetime) -> LicenceSnapshot:
        return LicenceSnapshot(
            customer_id=row["customer_id"],
            customer_code=row["customer_code"],
            customer_status=row["customer_status"],
            valid_from=row["valid_from"],
            valid_until=row["valid_until"],
            grace_days=row["grace_days"],
            modules=frozenset(row["modules"]),
            max_sites=row["max_sites"],
            max_users=row["max_users"],
            gxp_mode=row["gxp_mode"],
            gxp_locked=row["gxp_locked"],
            placement=row["placement"],
            db=DatabaseLocation(
                cluster_ref=row["cluster_ref"],
                pooler_endpoint=row["pooler_endpoint"],
                database_name=row["database_name"],
                app_role=row["app_role"],
                secret_ref=row["secret_ref"],
                schema_version=row["schema_version"],
                status=row["database_status"],
            ),
            fetched_at=fetched_at,
            feed_seq=row["feed_seq"],
        )

    async def get_snapshot(self, customer_id: UUID) -> LicenceSnapshot | None:
        """Snapshot of a licensed customer, or None if the customer is unknown or was never
        licensed (still provisioning)."""
        async with self._engine.connect() as conn:
            row = (
                (await conn.execute(text(_SNAPSHOT_SQL + " AND c.id = :id"), {"id": customer_id}))
                .mappings()
                .first()
            )
        return self._to_snapshot(row, self._clock.now()) if row else None

    async def get_provisioning_snapshot(self, customer_id: UUID) -> LicenceSnapshot | None:
        """Snapshot of a customer that is still provisioning, available only while its run is
        at the super-admin step (LLD 6.6 step 6 comes before activation, step 7). It lets Core
        reach the new database for exactly that step; afterwards, as before it, the customer
        has no snapshot until activated."""
        async with self._engine.connect() as conn:
            row = (
                (await conn.execute(text(_PROVISIONING_SNAPSHOT_SQL), {"id": customer_id})).mappings().first()
            )
        return self._to_snapshot(row, self._clock.now()) if row else None

    async def list_snapshots(self) -> list[LicenceSnapshot]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(text(_SNAPSHOT_SQL + " ORDER BY c.code"))).mappings().all()
        now = self._clock.now()
        return [self._to_snapshot(row, now) for row in rows]

    async def list_directory(self) -> list[DirectoryBundleEntry]:
        """Resolvable login-directory entries by lookup hash, for the snapshot bundle (AD-79)."""
        async with self._engine.connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text(
                            "SELECT encode(lookup_hash, 'hex') AS lookup_hash, customer_id, principal_type, "
                            "principal_id, status FROM platform.login_directory "
                            "WHERE status IN ('active', 'disabled') AND lookup_hash IS NOT NULL "
                            "ORDER BY lookup_hash"
                        )
                    )
                )
                .mappings()
                .all()
            )
        return [DirectoryBundleEntry(**row) for row in rows]

    async def changes(self, after_seq: int | None, limit: int = MAX_CHANGES_PAGE) -> ChangesResponse:
        """Change feed in commit order. Without ``after_seq`` only the head position is returned,
        which is where a newly started process begins listening."""
        limit = max(1, min(limit, MAX_CHANGES_PAGE))
        async with self._engine.connect() as conn:
            head = int(
                (
                    await conn.execute(text("SELECT COALESCE(max(seq), 0) FROM platform.change_feed"))
                ).scalar_one()
            )
            if after_seq is None:
                return ChangesResponse(entries=[], head_seq=head)
            rows = (
                (
                    await conn.execute(
                        text(
                            "SELECT seq, customer_id, change_type, changed_at FROM platform.change_feed "
                            "WHERE seq > :after ORDER BY seq LIMIT :limit"
                        ),
                        {"after": after_seq, "limit": limit},
                    )
                )
                .mappings()
                .all()
            )
        entries = [ChangeFeedEntry(**row) for row in rows]
        return ChangesResponse(entries=entries, head_seq=max(head, entries[-1].seq if entries else 0))
