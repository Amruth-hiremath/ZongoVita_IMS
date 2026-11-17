"""Wire models of the Platform Service's narrow, product-neutral interface (AD-12, LLD 6.8).

Resolve login, licence snapshot, database location, change feed. Nothing here is IMS-specific,
so another ZongoVita product can adopt the same service.
"""

from datetime import datetime
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
    """One login-directory row as carried in the snapshot bundle (hash only, no identifier)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    login_hash: str = Field(description="hex HMAC-SHA256(pepper, normalised identifier)")
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
