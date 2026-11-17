"""Unit of work (AD-08, LD-02).

Each request or job runs in one unit of work: a single customer-database transaction that
carries the change, its audit entries, any electronic signatures and its outbox events.
Services never commit; the kernel commits once at the end, or rolls everything back.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncConnection

from ims_common.clock import Clock
from ims_core.kernel.audit import AuditWriter
from ims_core.kernel.context import TenantContext
from ims_core.kernel.db import DatabaseRouter
from ims_core.kernel.grants import NO_GRANTS, Grants
from ims_core.kernel.outbox import OutboxWriter

log = logging.getLogger("ims.uow")

AfterCommit = Callable[[], Awaitable[None]]


class UnitOfWork:
    """What a service receives: the customer's connection plus audit and event writers."""

    def __init__(self, ctx: TenantContext, conn: AsyncConnection, clock: Clock) -> None:
        self.ctx = ctx
        self.db = conn
        self.clock = clock
        self.audit = AuditWriter(ctx, conn)
        self.events = OutboxWriter(ctx, conn)
        #: Effective permissions of the principal, set by pipeline step 8 (authorise). Jobs and
        #: credential flows act as the system or as a just-identified user and have none.
        self.grants: Grants = NO_GRANTS
        self._after_commit: list[AfterCommit] = []

    def on_commit(self, callback: AfterCommit) -> None:
        """Run ``callback`` only if, and after, the transaction commits (cache invalidation,
        work-pending hints). It must not be needed for correctness: it can be lost on a crash."""
        self._after_commit.append(callback)

    async def run_after_commit(self) -> None:
        callbacks, self._after_commit = self._after_commit, []
        for callback in callbacks:
            try:
                await callback()
            except Exception:
                log.exception("after-commit callback failed")


@contextlib.asynccontextmanager
async def unit_of_work(
    router: DatabaseRouter, ctx: TenantContext, clock: Clock, *, read_only: bool = False
) -> AsyncIterator[UnitOfWork]:
    """Open a unit of work outside the HTTP pipeline (jobs, login flows). Commits on a clean
    exit, rolls back on an exception, then runs after-commit callbacks."""
    async with router.transaction(ctx, read_only=read_only) as conn:
        uow = UnitOfWork(ctx, conn, clock)
        yield uow
    await uow.run_after_commit()
