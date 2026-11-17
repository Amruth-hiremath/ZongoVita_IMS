"""Wire models of the Platform Service's narrow, product-neutral interface (AD-12, LLD 6.8).

Resolve login, licence snapshot, database location, change feed. Nothing here is IMS-specific,
so another ZongoVita product can adopt the same service.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ims_contracts.enums import ChangeType
from ims_contracts.licence import LicenceSnapshot

SERVICE_AUDIENCE_PLATFORM_INTERNAL = "platform-internal"


class ChangeFeedEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    seq: int
    customer_id: UUID
    change_type: ChangeType
    changed_at: datetime


class ChangesResponse(BaseModel):
    """GET /internal/v1/changes?after_seq=

    ``head_seq`` is the highest sequence number committed when the page was read. Entries are in
    commit order and never appear below a sequence number already returned.
    """

    model_config = ConfigDict(extra="ignore")

    entries: list[ChangeFeedEntry]
    head_seq: int = Field(ge=0)


class DirectoryBundleEntry(BaseModel):
    """One login-directory row as carried in the snapshot bundle (hash only, no identifier).

    Keyed by the lookup hash, which products can compute; the pepper-keyed login hash stays inside
    the Platform Service (LD-10).
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    lookup_hash: str = Field(description="hex HMAC-SHA256(directory lookup key, normalised identifier)")
    customer_id: UUID
    principal_type: str
    principal_id: UUID
    status: str


class SnapshotBundle(BaseModel):
    """Last known-good store for processes that start during a Registry outage (LD-78)."""

    model_config = ConfigDict(extra="ignore")

    format_version: int = 1
    generated_at: datetime
    feed_seq: int
    snapshots: list[LicenceSnapshot]
    directory: list[DirectoryBundleEntry]


# --------------------------------------------------------------------------- login directory
DirectoryPrincipalType = Literal["user", "api_client"]
DirectoryStatus = Literal["reserved", "active", "disabled"]


class DirectoryResolveRequest(BaseModel):
    """POST /internal/v1/directory/resolve"""

    model_config = ConfigDict(extra="forbid")

    identifier: str = Field(min_length=1, max_length=320)


class DirectoryEntry(BaseModel):
    """Which customer and principal an identifier belongs to. Only active and disabled entries
    resolve; a reservation is not yet a principal anyone can sign in as."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    customer_id: UUID
    principal_type: DirectoryPrincipalType
    principal_id: UUID
    status: DirectoryStatus


class DirectoryReservationRequest(BaseModel):
    """POST /internal/v1/directory/reservations: hold an identifier for a principal being created."""

    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    principal_type: DirectoryPrincipalType
    principal_id: UUID
    identifier: str = Field(min_length=1, max_length=320)


class DirectoryReservationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: DirectoryStatus
    reserved_until: datetime | None


class DirectoryActivationRequest(BaseModel):
    """POST /internal/v1/directory/{principal_id}/activate (activate, or re-reserve and activate)."""

    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    principal_type: DirectoryPrincipalType
    identifier: str = Field(min_length=1, max_length=320)


class DirectoryDisableRequest(BaseModel):
    """POST /internal/v1/directory/{principal_id}/disable"""

    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    principal_type: DirectoryPrincipalType


class DirectoryListing(BaseModel):
    """GET /internal/v1/directory?customer_id=: one customer's entries, for reconciliation."""

    model_config = ConfigDict(extra="ignore")

    entries: list[DirectoryEntry]
