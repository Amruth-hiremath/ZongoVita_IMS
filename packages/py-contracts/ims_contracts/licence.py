"""Licence snapshot and the licence state machine (HLD section 5, AD-78; LLD 6.4).

The snapshot is the unit the Licence Registry hands to products. Licence state is never
stored: every process derives it from the snapshot and its own clock, so grace and read-only
start on time even if the Registry is unreachable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ims_contracts.enums import CustomerStatus, DatabaseStatus, Placement


class LicenceState(StrEnum):
    ACTIVE = "active"
    GRACE = "grace"
    READ_ONLY = "read_only"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


class DatabaseLocation(BaseModel):
    """Where a customer's database is and how to authenticate to it.

    Carries a reference to the credential in the secrets store, never the credential (LD-12).
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    cluster_ref: str
    pooler_endpoint: str = Field(description="host:port of the cluster's transaction-mode pooler")
    database_name: str
    app_role: str
    secret_ref: str
    schema_version: str | None
    status: DatabaseStatus

    @property
    def pooler_host(self) -> str:
        return self.pooler_endpoint.rsplit(":", 1)[0]

    @property
    def pooler_port(self) -> int:
        return int(self.pooler_endpoint.rsplit(":", 1)[1])

    @field_validator("pooler_endpoint")
    @classmethod
    def _endpoint_has_port(cls, value: str) -> str:
        host, sep, port = value.rpartition(":")
        if not sep or not host or not port.isdigit():
            raise ValueError("pooler_endpoint must be host:port")
        return value

    def routing_key(self) -> tuple[str, str, str, str]:
        """Changes when the customer must be reached differently (for example after a move)."""
        return (self.pooler_endpoint, self.database_name, self.app_role, self.secret_ref)


class LicenceSnapshot(BaseModel):
    """Everything a product needs to enforce one customer's licence and reach its database."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    customer_id: UUID
    customer_code: str
    customer_status: CustomerStatus
    valid_from: datetime
    valid_until: datetime
    grace_days: int = Field(ge=0)
    modules: frozenset[str]
    max_sites: int = Field(ge=0)
    max_users: int = Field(ge=0)
    gxp_mode: bool
    gxp_locked: bool
    placement: Placement
    db: DatabaseLocation
    fetched_at: datetime
    feed_seq: int = Field(ge=0, description="Change-feed position this snapshot is consistent with")

    _aware = field_validator("valid_from", "valid_until", "fetched_at")(_require_aware)

    @property
    def grace_ends_at(self) -> datetime:
        return self.valid_until + timedelta(days=self.grace_days)


def derive_state(snapshot: LicenceSnapshot, now: datetime) -> LicenceState:
    """The licence state machine of LLD 6.4, evaluated locally.

    terminated if customer_status = terminated
    suspended  if customer_status = suspended
    active     if now < valid_until
    grace      if now < valid_until + grace_days
    read_only  otherwise
    """
    now = _require_aware(now)
    if snapshot.customer_status is CustomerStatus.TERMINATED:
        return LicenceState.TERMINATED
    if snapshot.customer_status is CustomerStatus.SUSPENDED:
        return LicenceState.SUSPENDED
    if now < snapshot.valid_until:
        return LicenceState.ACTIVE
    if now < snapshot.grace_ends_at:
        return LicenceState.GRACE
    return LicenceState.READ_ONLY


#: States in which the customer may not use the product at all.
BLOCKED_STATES = frozenset({LicenceState.SUSPENDED, LicenceState.TERMINATED})
