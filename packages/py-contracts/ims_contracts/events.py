"""Published event envelope (LLD section 13, AD-53, AD-85).

Envelope: id, type, version, seq, occurred_at, customer (code), subject {type, id, version},
trace_id, data. Consumers deduplicate on ``id`` and order per subject by ``subject.version``.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventSubject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str
    id: str
    version: int = Field(ge=1, description="Increases with every change to the subject")


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    type: str = Field(pattern=r"^[a-z_]+(\.[a-z_]+)+$")
    version: int = Field(ge=1, description="Increases only for incompatible changes to the type")
    seq: int = Field(description="Per-customer allocation order; not commit order")
    occurred_at: datetime
    customer: str = Field(description="Customer code")
    subject: EventSubject
    trace_id: str | None = None
    data: dict[str, Any]
