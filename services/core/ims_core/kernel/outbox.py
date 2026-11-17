"""Transactional outbox, write side (AD-51, AD-85; LLD 5.4, section 13).

A business event is a row written by the business transaction itself, so an event exists if and
only if its change committed. Workers deliver it afterwards; integration failures therefore
never block a user transaction (AD-73).

The stored row is the envelope minus what the database or the dispatcher adds: ``seq``,
``txid`` and ``occurred_at`` are column defaults, and the customer code is added on the way out.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from ims_common.ids import uuid7
from ims_core.kernel import jsonutil
from ims_core.kernel.context import TenantContext

_EVENT_TYPE_RE = re.compile(r"^[a-z_]+(\.[a-z_]+)+$")

_INSERT = text(
    """
    INSERT INTO integration.outbox_events
        (id, event_type, event_version, subject_type, subject_id, subject_version, payload, trace_id)
    VALUES (:id, :event_type, :event_version, :subject_type, :subject_id, :subject_version,
            CAST(:payload AS jsonb), :trace_id)
    """
)


class OutboxWriter:
    def __init__(self, ctx: TenantContext, conn: AsyncConnection) -> None:
        self._ctx = ctx
        self._conn = conn
        self.events_written = 0

    async def publish(
        self,
        *,
        event_type: str,
        subject_type: str,
        subject_id: UUID | str,
        subject_version: int,
        data: Mapping[str, Any],
        event_version: int = 1,
    ) -> UUID:
        """Record an event about ``subject`` at ``subject_version``.

        ``subject_version`` must be the subject row's version after this change: consumers order
        events per subject by it and discard anything not newer than what they last applied
        (LD-87). ``event_version`` rises only for incompatible changes to the event type.
        """
        if not _EVENT_TYPE_RE.fullmatch(event_type):
            raise ValueError(f"invalid event type: {event_type!r}")
        if subject_version < 1:
            raise ValueError("subject_version starts at 1")
        event_id = uuid7()
        await self._conn.execute(
            _INSERT,
            {
                "id": event_id,
                "event_type": event_type,
                "event_version": event_version,
                "subject_type": subject_type,
                "subject_id": str(subject_id),
                "subject_version": subject_version,
                "payload": jsonutil.dumps(data),
                "trace_id": self._ctx.trace_id,
            },
        )
        self.events_written += 1
        return event_id
