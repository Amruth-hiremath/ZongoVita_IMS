"""Login Directory (AD-20; LLD 4, 6.3, 6.8).

Maps each login identifier to exactly one customer and principal, so a product can find the
customer before it checks a credential, without moving credentials or profiles out of the
customer's database. Only keyed hashes of identifiers are stored.

Lifecycle of an entry: ``reserved`` (a principal is being created; held for 15 minutes) ->
``active`` (resolvable; the principal can sign in) -> ``disabled`` (resolvable, refused). An
expired reservation may be taken over by another principal. Every change is audited and appended
to the change feed (type ``directory``) in the same transaction, so product caches are evicted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ims_common.clock import Clock, SystemClock
from ims_common.identifiers import InvalidIdentifierError, keyed_hash, normalise_login_identifier
from ims_common.pg import SQLSTATE_UNIQUE_VIOLATION, sqlstate_of
from ims_common.problem import DomainError
from ims_contracts.enums import ChangeType
from ims_contracts.errors import ErrorCode, FieldError
from ims_contracts.platform_api import DirectoryEntry, DirectoryReservationResponse
from ims_platform.registry import Actor, audit_change, notify_change

RESERVATION_TTL = timedelta(minutes=15)  # LLD 6.3

_SELECT_BY_HASH = text(
    "SELECT login_hash, customer_id, principal_type, principal_id, status, reserved_until "
    "FROM platform.login_directory WHERE login_hash = :h FOR UPDATE"
)
_SELECT_BY_PRINCIPAL = text(
    "SELECT login_hash, customer_id, principal_type, principal_id, status, reserved_until "
    "FROM platform.login_directory "
    "WHERE customer_id = :c AND principal_type = :t AND principal_id = :p FOR UPDATE"
)
_RESOLVE = text(
    "SELECT customer_id, principal_type, principal_id, status FROM platform.login_directory "
    "WHERE login_hash = :h AND status IN ('active', 'disabled')"
)
_LIST = text(
    "SELECT customer_id, principal_type, principal_id, status FROM platform.login_directory "
    "WHERE customer_id = :c ORDER BY principal_type, principal_id"
)


@dataclass(frozen=True)
class _Row:
    login_hash: bytes
    customer_id: UUID
    principal_type: str
    principal_id: UUID
    status: str
    reserved_until: datetime | None

    def belongs_to(self, customer_id: UUID, principal_type: str, principal_id: UUID) -> bool:
        return (self.customer_id, self.principal_type, self.principal_id) == (
            customer_id,
            principal_type,
            principal_id,
        )

    def expired_reservation(self, now: datetime) -> bool:
        return self.status == "reserved" and self.reserved_until is not None and self.reserved_until <= now


def _row(mapping: Any) -> _Row | None:
    if mapping is None:
        return None
    return _Row(
        login_hash=bytes(mapping["login_hash"]),
        customer_id=mapping["customer_id"],
        principal_type=mapping["principal_type"],
        principal_id=mapping["principal_id"],
        status=mapping["status"],
        reserved_until=mapping["reserved_until"],
    )


def _principal_ref(row: _Row) -> str:
    return f"{row.customer_id}/{row.principal_type}:{row.principal_id}"


def _taken() -> DomainError:
    return DomainError(ErrorCode.LOGIN_IDENTIFIER_TAKEN)


class DirectoryService:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        pepper: bytes,
        lookup_key: bytes,
        clock: Clock | None = None,
        reservation_ttl: timedelta = RESERVATION_TTL,
    ) -> None:
        self._engine = engine
        self._pepper = pepper
        self._lookup_key = lookup_key
        self._clock = clock or SystemClock()
        self._ttl = reservation_ttl

    # -------------------------------------------------------------------------------- hashing
    def _hashes(self, identifier: str) -> tuple[bytes, bytes]:
        try:
            normalise_login_identifier(identifier)
        except InvalidIdentifierError as exc:
            raise DomainError(
                ErrorCode.VALIDATION_FAILED, errors=[FieldError(field="identifier", message=str(exc))]
            ) from None
        return keyed_hash(self._pepper, identifier), keyed_hash(self._lookup_key, identifier)

    # ---------------------------------------------------------------------------- row access
    @staticmethod
    async def _by_hash(conn: AsyncConnection, login_hash: bytes) -> _Row | None:
        result = await conn.execute(_SELECT_BY_HASH, {"h": login_hash})
        return _row(result.mappings().first())

    @staticmethod
    async def _by_principal(
        conn: AsyncConnection, customer_id: UUID, principal_type: str, principal_id: UUID
    ) -> _Row | None:
        result = await conn.execute(
            _SELECT_BY_PRINCIPAL,
            {"c": customer_id, "t": principal_type, "p": principal_id},
        )
        return _row(result.mappings().first())

    @staticmethod
    async def _require_customer(conn: AsyncConnection, customer_id: UUID) -> None:
        exists = (
            await conn.execute(text("SELECT 1 FROM platform.customers WHERE id = :id"), {"id": customer_id})
        ).scalar_one_or_none()
        if exists is None:
            raise DomainError(ErrorCode.NOT_FOUND, "customer not found")

    async def _record(
        self,
        conn: AsyncConnection,
        actor: Actor,
        action: str,
        customer_id: UUID,
        principal_type: str,
        principal_id: UUID,
        before: dict[str, Any] | None,
        after: dict[str, Any],
    ) -> None:
        await audit_change(
            conn,
            actor,
            action,
            "login_directory",
            f"{principal_type}:{principal_id}",
            customer_id,
            before=before,
            after=after,
        )
        await notify_change(conn, customer_id, ChangeType.DIRECTORY)

    # -------------------------------------------------------------------------------- reads
    async def resolve(self, identifier: str) -> DirectoryEntry | None:
        """Customer and principal of an identifier; None if unknown or only reserved."""
        try:
            login_hash = keyed_hash(self._pepper, identifier)
        except InvalidIdentifierError:
            return None
        async with self._engine.connect() as conn:
            row = (await conn.execute(_RESOLVE, {"h": login_hash})).mappings().first()
        return DirectoryEntry(**row) if row else None

    async def list_for_customer(self, customer_id: UUID) -> list[DirectoryEntry]:
        """Every entry of one customer, for reconciliation (LLD 6.3)."""
        async with self._engine.connect() as conn:
            rows = (await conn.execute(_LIST, {"c": customer_id})).mappings().all()
        return [DirectoryEntry(**row) for row in rows]

    # ----------------------------------------------------------------------------- commands
    async def reserve(
        self,
        *,
        customer_id: UUID,
        principal_type: str,
        principal_id: UUID,
        identifier: str,
        actor: Actor,
    ) -> DirectoryReservationResponse:
        """Hold the identifier for a principal being created (LLD 6.3, step "reserve").

        Returns the reservation and its expiry, or status ``active`` if the principal already holds
        the identifier (idempotent). Raises 409 LOGIN_IDENTIFIER_TAKEN if any other principal of any
        customer holds it, unless that holder's reservation has expired.
        """
        login_hash, lookup_hash = self._hashes(identifier)
        now = self._clock.now()
        until = now + self._ttl
        try:
            async with self._engine.begin() as conn:
                await self._require_customer(conn, customer_id)
                row = await self._by_hash(conn, login_hash)
                if row is None:
                    inserted = (
                        await conn.execute(
                            text(
                                "INSERT INTO platform.login_directory "
                                "(login_hash, lookup_hash, customer_id, principal_type, principal_id, "
                                " status, reserved_until) "
                                "VALUES (:h, :k, :c, :t, :p, 'reserved', :u) "
                                "ON CONFLICT (login_hash) DO NOTHING RETURNING 1"
                            ),
                            {
                                "h": login_hash,
                                "k": lookup_hash,
                                "c": customer_id,
                                "t": principal_type,
                                "p": principal_id,
                                "u": until,
                            },
                        )
                    ).scalar_one_or_none()
                    if inserted is None:  # a concurrent reservation won the race
                        raise _taken()
                    await self._record(
                        conn,
                        actor,
                        "directory.reserved",
                        customer_id,
                        principal_type,
                        principal_id,
                        None,
                        {"status": "reserved", "reserved_until": until},
                    )
                    return DirectoryReservationResponse(status="reserved", reserved_until=until)
                if row.belongs_to(customer_id, principal_type, principal_id):
                    if row.status == "active":
                        return DirectoryReservationResponse(status="active", reserved_until=None)
                    before = {"status": row.status, "reserved_until": row.reserved_until}
                elif row.expired_reservation(now):
                    before = {
                        "status": row.status,
                        "reserved_until": row.reserved_until,
                        "previous_principal": _principal_ref(row),
                    }
                else:
                    raise _taken()
                await conn.execute(
                    text(
                        "UPDATE platform.login_directory SET customer_id = :c, principal_type = :t, "
                        "principal_id = :p, lookup_hash = :k, status = 'reserved', reserved_until = :u, "
                        "updated_at = now() WHERE login_hash = :h"
                    ),
                    {
                        "c": customer_id,
                        "t": principal_type,
                        "p": principal_id,
                        "k": lookup_hash,
                        "u": until,
                        "h": login_hash,
                    },
                )
                await self._record(
                    conn,
                    actor,
                    "directory.reserved",
                    customer_id,
                    principal_type,
                    principal_id,
                    before,
                    {"status": "reserved", "reserved_until": until},
                )
                return DirectoryReservationResponse(status="reserved", reserved_until=until)
        except IntegrityError as exc:
            if sqlstate_of(exc) == SQLSTATE_UNIQUE_VIOLATION:
                # The principal already holds a different identifier.
                raise DomainError(
                    ErrorCode.INVALID_STATE_TRANSITION, "this principal already has a login identifier"
                ) from exc
            raise

    async def activate(
        self,
        *,
        customer_id: UUID,
        principal_type: str,
        principal_id: UUID,
        identifier: str,
        actor: Actor,
    ) -> None:
        """Make the principal's entry resolvable. Idempotent.

        Activate-or-re-reserve (LLD 6.3): succeeds if the identifier is still free, still reserved
        for this principal (even past its expiry), or already active for it. Raises 409
        LOGIN_IDENTIFIER_TAKEN if another principal took it meanwhile.
        """
        login_hash, lookup_hash = self._hashes(identifier)
        now = self._clock.now()
        try:
            async with self._engine.begin() as conn:
                await self._require_customer(conn, customer_id)
                own = await self._by_principal(conn, customer_id, principal_type, principal_id)
                if own is not None:
                    if own.login_hash != login_hash:
                        raise DomainError(
                            ErrorCode.INVALID_STATE_TRANSITION, "the principal holds a different identifier"
                        )
                    if own.status == "active":
                        return
                    if own.status == "disabled":
                        raise DomainError(
                            ErrorCode.INVALID_STATE_TRANSITION,
                            "the entry is disabled; reserve it again first",
                        )
                    await conn.execute(
                        text(
                            "UPDATE platform.login_directory SET status = 'active', reserved_until = NULL, "
                            "lookup_hash = :k, updated_at = now() WHERE login_hash = :h"
                        ),
                        {"k": lookup_hash, "h": login_hash},
                    )
                    before: dict[str, Any] | None = {
                        "status": own.status,
                        "reserved_until": own.reserved_until,
                    }
                else:
                    other = await self._by_hash(conn, login_hash)
                    if other is None:
                        inserted = (
                            await conn.execute(
                                text(
                                    "INSERT INTO platform.login_directory "
                                    "(login_hash, lookup_hash, customer_id, principal_type, principal_id, "
                                    " status) "
                                    "VALUES (:h, :k, :c, :t, :p, 'active') "
                                    "ON CONFLICT (login_hash) DO NOTHING RETURNING 1"
                                ),
                                {
                                    "h": login_hash,
                                    "k": lookup_hash,
                                    "c": customer_id,
                                    "t": principal_type,
                                    "p": principal_id,
                                },
                            )
                        ).scalar_one_or_none()
                        if inserted is None:
                            raise _taken()
                        before = None
                    elif other.expired_reservation(now):
                        await conn.execute(
                            text(
                                "UPDATE platform.login_directory SET customer_id = :c, principal_type = :t, "
                                "principal_id = :p, lookup_hash = :k, status = 'active', "
                                "reserved_until = NULL, "
                                "updated_at = now() WHERE login_hash = :h"
                            ),
                            {
                                "c": customer_id,
                                "t": principal_type,
                                "p": principal_id,
                                "k": lookup_hash,
                                "h": login_hash,
                            },
                        )
                        before = {
                            "status": other.status,
                            "previous_principal": _principal_ref(other),
                        }
                    else:
                        raise _taken()
                await self._record(
                    conn,
                    actor,
                    "directory.activated",
                    customer_id,
                    principal_type,
                    principal_id,
                    before,
                    {"status": "active"},
                )
        except IntegrityError as exc:
            if sqlstate_of(exc) == SQLSTATE_UNIQUE_VIOLATION:
                raise DomainError(
                    ErrorCode.INVALID_STATE_TRANSITION, "this principal already has a login identifier"
                ) from exc
            raise

    async def disable(
        self, *, customer_id: UUID, principal_type: str, principal_id: UUID, actor: Actor
    ) -> None:
        """Stop the principal from signing in (deactivation, LLD 6.3). Idempotent."""
        async with self._engine.begin() as conn:
            own = await self._by_principal(conn, customer_id, principal_type, principal_id)
            if own is None:
                raise DomainError(ErrorCode.NOT_FOUND, "no directory entry for this principal")
            if own.status == "disabled":
                return
            await conn.execute(
                text(
                    "UPDATE platform.login_directory SET status = 'disabled', reserved_until = NULL, "
                    "updated_at = now() WHERE login_hash = :h"
                ),
                {"h": own.login_hash},
            )
            await self._record(
                conn,
                actor,
                "directory.disabled",
                customer_id,
                principal_type,
                principal_id,
                {"status": own.status},
                {"status": "disabled"},
            )
