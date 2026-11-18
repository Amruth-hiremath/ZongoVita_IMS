"""Request and response bodies of the organisation endpoints (LLD 5.1, 12)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


Code = Field(min_length=1, max_length=32, description="Letters, digits, '.', '_' or '-'; fixed once created")
Name = Field(min_length=1, max_length=200)


class SiteOut(BaseModel):
    id: UUID
    code: str
    name: str
    timezone: str = Field(description="IANA timezone for display and daily jobs (LLD 3)")
    status: Literal["staged", "active", "inactive"]
    created_at: datetime
    updated_at: datetime
    version: int


class SitePage(BaseModel):
    items: list[SiteOut]
    next_cursor: str | None


class LocationSeed(_Body):
    code: str = Code
    name: str = Name


class CreateSite(_Body):
    code: str = Code
    name: str = Name
    timezone: str = Field(min_length=1, max_length=64)
    status: Literal["staged", "active"] = "staged"
    default_location: LocationSeed = Field(
        description="Every site has exactly one default location (LLD 5.1)"
    )


class UpdateSite(_Body):
    name: str = Name
    timezone: str = Field(min_length=1, max_length=64)


class LocationOut(BaseModel):
    id: UUID
    site_id: UUID
    code: str
    name: str
    is_default: bool
    status: Literal["active", "inactive"]
    created_at: datetime
    updated_at: datetime
    version: int


class LocationPage(BaseModel):
    items: list[LocationOut]
    next_cursor: str | None


class CreatedSite(BaseModel):
    site: SiteOut
    default_location: LocationOut


class CreateLocation(_Body):
    site_id: UUID
    code: str = Code
    name: str = Name


class UpdateName(_Body):
    name: str = Name


class DepartmentOut(BaseModel):
    id: UUID
    code: str
    name: str
    status: Literal["active", "inactive"]
    created_at: datetime
    updated_at: datetime
    version: int


class DepartmentPage(BaseModel):
    items: list[DepartmentOut]
    next_cursor: str | None


class CreateDepartment(_Body):
    code: str = Code
    name: str = Name
