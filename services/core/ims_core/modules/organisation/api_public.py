"""Organisation reference data on the public API (LLD 12 public table: "GET sites, locations |
Reference data | Authenticated"). Read-only; licence module ims.integration (LD-72)."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Query
from fastapi.responses import JSONResponse

from ims_contracts.enums import LicenceModule
from ims_core.kernel.authn import AUDIENCE_API
from ims_core.kernel.paging import After, Limit, page
from ims_core.kernel.routes import Authenticated, ImsRouter, Uow, declare
from ims_core.modules.organisation import repository
from ims_core.modules.organisation import schemas as s
from ims_core.modules.organisation.api_ui import location_out, site_out

router = ImsRouter(
    prefix="/api/v1", audience=AUDIENCE_API, module=LicenceModule.INTEGRATION, tags=["reference"]
)


@router.get("/sites", response_model=s.SitePage)
@declare(access=Authenticated(), read_only_ok=True)
async def list_sites(
    uow: Uow,
    after: After,
    limit: Limit,
    status: Annotated[Literal["staged", "active", "inactive"] | None, Query()] = None,
) -> JSONResponse:
    rows = await repository.list_sites(uow.db, status=status, after=after, limit=limit + 1)
    items, cursor = page(rows, limit, lambda row: row.id)
    return JSONResponse(
        s.SitePage(items=[site_out(r) for r in items], next_cursor=cursor).model_dump(mode="json")
    )


@router.get("/locations", response_model=s.LocationPage)
@declare(access=Authenticated(), read_only_ok=True)
async def list_locations(
    uow: Uow,
    after: After,
    limit: Limit,
    site_id: UUID | None = None,
    status: Annotated[Literal["active", "inactive"] | None, Query()] = None,
) -> JSONResponse:
    rows = await repository.list_locations(
        uow.db, site_id=site_id, status=status, after=after, limit=limit + 1
    )
    items, cursor = page(rows, limit, lambda row: row.id)
    return JSONResponse(
        s.LocationPage(items=[location_out(r) for r in items], next_cursor=cursor).model_dump(mode="json")
    )
