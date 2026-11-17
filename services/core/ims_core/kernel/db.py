"""Database routing (AD-16, AD-18, AD-21, AD-80; LLD 6.5).

One customer, one database, one credential. ``DatabaseRouter.transaction`` is the only way to
obtain a customer-database connection in Core, and it requires a ``TenantContext``: code that
has no resolved customer cannot reach any customer's data.

Each process keeps one small client pool per customer towards that customer's cluster pooler.
Server connections are budgeted by the pooler, per customer, not here.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ims_common.clock import Clock
from ims_common.pg import AUTH_FAILURE_SQLSTATES, create_pooler_engine, sqlstate_of
from ims_common.problem import DomainError
from ims_common.secrets import SecretsStore
from ims_contracts.enums import DatabaseStatus
from ims_contracts.errors import ErrorCode
from ims_contracts.licence import DatabaseLocation, LicenceSnapshot
from ims_core.kernel.context import TenantContext
from ims_core.kernel.settings import CoreSettings
from ims_core.schema.version import SCHEMA_SUPPORTED

log = logging.getLogger("ims.db")

#: A database being migrated keeps serving: migrations are online and expand-only (LLD 6.7).
_SERVABLE_STATUSES = frozenset({DatabaseStatus.READY, DatabaseStatus.MIGRATING})


@dataclass
class _Pool:
    routing_key: tuple[str, str, str, str]
    engine: AsyncEngine


def _is_auth_failure(exc: BaseException) -> bool:
    if sqlstate_of(exc) in AUTH_FAILURE_SQLSTATES:
        return True
    message = str(exc).lower()
    return "authentication failed" in message or "password authentication" in message


class DatabaseRouter:
    def __init__(self, secrets: SecretsStore, settings: CoreSettings, clock: Clock) -> None:
        self._secrets = secrets
        self._settings = settings
        self._clock = clock
        self._pools: dict[UUID, _Pool] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}
        self._credentials: dict[str, tuple[str, float]] = {}

    def busy(self, detail: str) -> DomainError:
        return DomainError(
            ErrorCode.DB_BUSY,
            detail,
            headers={"Retry-After": str(self._settings.db_busy_retry_after_seconds)},
        )

    # ------------------------------------------------------------------- step 5, static part
    def check_servable(self, snapshot: LicenceSnapshot) -> None:
        """Refuse before connecting if this release cannot serve the customer's database."""
        db = snapshot.db
        if db.status not in _SERVABLE_STATUSES:
            raise self.busy("the customer database is not available")
        if db.schema_version not in SCHEMA_SUPPORTED:
            raise DomainError(ErrorCode.SCHEMA_VERSION_UNSUPPORTED)

    # --------------------------------------------------------------------------- credentials
    async def _password(self, secret_ref: str, *, refresh: bool = False) -> str:
        cached = self._credentials.get(secret_ref)
        now = self._clock.monotonic()
        if cached and not refresh and now - cached[1] < self._settings.db_credential_cache_seconds:
            return cached[0]
        secret = await self._secrets.get(secret_ref)
        self._credentials[secret_ref] = (secret["password"], now)
        return secret["password"]

    def _create_engine(self, db: DatabaseLocation, password: str) -> AsyncEngine:
        return create_pooler_engine(
            host=db.pooler_host,
            port=db.pooler_port,
            database=db.database_name,
            user=db.app_role,
            password=password,
            application_name=f"{self._settings.service_name}/{self._settings.instance}",
            pool_size=self._settings.db_pool_size,
            max_overflow=self._settings.db_max_overflow,
            pool_timeout_s=self._settings.db_pool_timeout_seconds,
            sslmode=self._settings.db_sslmode,
        )

    async def _pool_for(self, ctx: TenantContext, *, refresh_credential: bool = False) -> AsyncEngine:
        db = ctx.snapshot.db
        key = db.routing_key()
        pool = self._pools.get(ctx.customer_id)
        if pool is not None and pool.routing_key == key and not refresh_credential:
            return pool.engine
        lock = self._locks.setdefault(ctx.customer_id, asyncio.Lock())
        async with lock:
            pool = self._pools.get(ctx.customer_id)
            if pool is not None and pool.routing_key == key and not refresh_credential:
                return pool.engine
            password = await self._password(db.secret_ref, refresh=refresh_credential)
            engine = self._create_engine(db, password)
            self._pools[ctx.customer_id] = _Pool(key, engine)
            if pool is not None:
                # The customer moved (placement change) or its credential rotated.
                await pool.engine.dispose()
            return engine

    async def _connect(self, ctx: TenantContext) -> AsyncConnection:
        engine = await self._pool_for(ctx)
        try:
            return await engine.connect()
        except PoolTimeoutError:
            raise self.busy("no database connection became available in time") from None
        except OperationalError as exc:
            if not _is_auth_failure(exc):
                raise self.busy("the database could not be reached") from exc
        # The credential was rejected: it may have been rotated. Re-read it once and retry.
        log.warning("database credential rejected; re-reading from the secrets store")
        engine = await self._pool_for(ctx, refresh_credential=True)
        try:
            return await engine.connect()
        except PoolTimeoutError:
            raise self.busy("no database connection became available in time") from None
        except OperationalError as exc:
            raise self.busy("the database could not be reached") from exc

    # --------------------------------------------------------------------------- connections
    @contextlib.asynccontextmanager
    async def transaction(
        self, ctx: TenantContext, *, read_only: bool = False
    ) -> AsyncIterator[AsyncConnection]:
        """One transaction on the context's customer database: commit on success, roll back on
        any exception. ``read_only`` makes PostgreSQL itself refuse writes (reads write nothing,
        AD-08)."""
        if not isinstance(ctx, TenantContext):
            raise TypeError("a resolved TenantContext is required to reach a customer database")
        self.check_servable(ctx.snapshot)
        conn = await self._connect(ctx)
        try:
            await conn.begin()
            if read_only:
                await conn.execute(text("SET TRANSACTION READ ONLY"))
            try:
                yield conn
            except BaseException:
                with contextlib.suppress(DBAPIError):
                    await conn.rollback()
                raise
            await conn.commit()
        finally:
            await conn.close()

    async def aclose(self) -> None:
        pools, self._pools = self._pools, {}
        for pool in pools.values():
            await pool.engine.dispose()
