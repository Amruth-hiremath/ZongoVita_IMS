"""Audit trail writer (AD-66; LLD 5.4, LD-82).

Who, what, when, before and after, request ID: written in the same transaction as the change,
into a table the application role can only append to. When, sequence and transaction ID are set
by the database, not by the application.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from ims_common.problem import DomainError
from ims_contracts.enums import ActorType
from ims_contracts.errors import ErrorCode
from ims_core.kernel import jsonutil
from ims_core.kernel.context import TenantContext

_INSERT = text(
    """
    INSERT INTO audit.audit_log
        (actor_type, actor_id, action, entity_type, entity_id, site_id, before, after, reason,
         request_id, source)
    VALUES (:actor_type, :actor_id, :action, :entity_type, :entity_id, :site_id,
            CAST(:before AS jsonb), CAST(:after AS jsonb), :reason, :request_id, :source)
    """
)


class AuditWriter:
    def __init__(self, ctx: TenantContext, conn: AsyncConnection) -> None:
        self._ctx = ctx
        self._conn = conn
        self.entries_written = 0

    async def record(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: UUID | str,
        before: Mapping[str, Any] | None = None,
        after: Mapping[str, Any] | None = None,
        site_id: UUID | None = None,
        reason: str | None = None,
        gmp_relevant: bool = False,
    ) -> None:
        """Append one audit entry.

        ``gmp_relevant`` marks changes that need a reason for change in GxP mode: item master and
        specification edits, verdicts and dispositions, approval decisions, count adjustments,
        approval-policy changes, role and permission changes. Customer configuration cannot
        switch this off.
        """
        reason = reason.strip() if reason else None
        if gmp_relevant and self._ctx.gxp_mode and not reason:
            raise DomainError(ErrorCode.REASON_REQUIRED)
        principal = self._ctx.principal
        await self._conn.execute(
            _INSERT,
            {
                "actor_type": (principal.actor_type if principal else ActorType.SYSTEM).value,
                "actor_id": principal.id if principal else None,
                "action": action,
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "site_id": site_id,
                "before": jsonutil.dumps(before) if before is not None else None,
                "after": jsonutil.dumps(after) if after is not None else None,
                "reason": reason or None,
                "request_id": self._ctx.request_id,
                "source": self._ctx.source,
            },
        )
        self.entries_written += 1
