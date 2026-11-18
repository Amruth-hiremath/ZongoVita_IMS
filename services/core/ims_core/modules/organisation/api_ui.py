"""Organisation endpoints of the UI API (LLD 12 route table).

| Endpoint                                                   | Rule                  |
| GET sites, locations, departments (reference data)         | Authenticated         |
| sites (create, edit, activate, deactivate)                 | org.site.manage       |
| locations (create, edit, make default, activate, deactivate)| org.location.manage  |
| departments (create, edit, activate, deactivate)           | org.department.manage |

Every state change is its own command sub-resource; edits need If-Match (LLD 12).
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ims_contracts.enums import LicenceModule
from ims_core.kernel.authn import AUDIENCE_UI
from ims_core.kernel.paging import After, Limit, page
from ims_core.kernel.routes import Authenticated, ImsRouter, Permission, Uow, declare
from ims_core.kernel.versioning import IfMatch, set_etag
from ims_core.modules.organisation import repository
from ims_core.modules.organisation import schemas as s
from ims_core.modules.organisation.repository import DepartmentRow, LocationRow, SiteRow
from ims_core.modules.organisation.service import LocationSeed, OrganisationService

router = ImsRouter(prefix="/ui/v1", audience=AUDIENCE_UI, module=LicenceModule.CORE, tags=["organisation"])

SITE_MANAGE = Permission("org.site.manage")
LOCATION_MANAGE = Permission("org.location.manage")
DEPARTMENT_MANAGE = Permission("org.department.manage")


def get_organisation(request: Request) -> OrganisationService:
    return request.app.state.organisation


Org = Annotated[OrganisationService, Depends(get_organisation)]


def site_out(row: SiteRow) -> s.SiteOut:
    return s.SiteOut(**row.__dict__)


def location_out(row: LocationRow) -> s.LocationOut:
    return s.LocationOut(**row.__dict__)


def department_out(row: DepartmentRow) -> s.DepartmentOut:
    return s.DepartmentOut(**row.__dict__)


def _json(model: BaseModel, *, status_code: int = 200, version: int | None = None) -> JSONResponse:
    response = JSONResponse(model.model_dump(mode="json"), status_code=status_code)
    if version is not None:
        set_etag(response, version)
    return response


# ------------------------------------------------------------------------------------ sites
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
    return _json(s.SitePage(items=[site_out(r) for r in items], next_cursor=cursor))


@router.get("/sites/{site_id}", response_model=s.SiteOut)
@declare(access=Authenticated(), read_only_ok=True)
async def get_site(site_id: UUID, uow: Uow, org: Org) -> JSONResponse:
    site = await org.get_site(uow, site_id)
    return _json(site_out(site), version=site.version)


@router.post("/sites", response_model=s.CreatedSite, status_code=201)
@declare(access=SITE_MANAGE, read_only_ok=False)
async def create_site(body: s.CreateSite, uow: Uow, org: Org) -> JSONResponse:
    site, location = await org.create_site(
        uow,
        code=body.code,
        name=body.name,
        timezone=body.timezone,
        status=body.status,
        default_location=LocationSeed(code=body.default_location.code, name=body.default_location.name),
    )
    created = s.CreatedSite(site=site_out(site), default_location=location_out(location))
    return _json(created, status_code=201, version=site.version)


@router.patch("/sites/{site_id}", response_model=s.SiteOut)
@declare(access=SITE_MANAGE, read_only_ok=False)
async def update_site(
    site_id: UUID, body: s.UpdateSite, version: IfMatch, uow: Uow, org: Org
) -> JSONResponse:
    site = await org.update_site(
        uow, site_id, expected_version=version, name=body.name, timezone=body.timezone
    )
    return _json(site_out(site), version=site.version)


@router.post("/sites/{site_id}/activate", response_model=s.SiteOut)
@declare(access=SITE_MANAGE, read_only_ok=False)
async def activate_site(site_id: UUID, uow: Uow, org: Org) -> JSONResponse:
    site = await org.change_site_status(uow, site_id, "active")
    return _json(site_out(site), version=site.version)


@router.post("/sites/{site_id}/deactivate", response_model=s.SiteOut)
@declare(access=SITE_MANAGE, read_only_ok=False)
async def deactivate_site(site_id: UUID, uow: Uow, org: Org) -> JSONResponse:
    site = await org.change_site_status(uow, site_id, "inactive")
    return _json(site_out(site), version=site.version)


# -------------------------------------------------------------------------------- locations
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
    return _json(s.LocationPage(items=[location_out(r) for r in items], next_cursor=cursor))


@router.get("/locations/{location_id}", response_model=s.LocationOut)
@declare(access=Authenticated(), read_only_ok=True)
async def get_location(location_id: UUID, uow: Uow, org: Org) -> JSONResponse:
    location = await org.get_location(uow, location_id)
    return _json(location_out(location), version=location.version)


@router.post("/locations", response_model=s.LocationOut, status_code=201)
@declare(access=LOCATION_MANAGE, read_only_ok=False)
async def create_location(body: s.CreateLocation, uow: Uow, org: Org) -> JSONResponse:
    location = await org.create_location(uow, site_id=body.site_id, code=body.code, name=body.name)
    return _json(location_out(location), status_code=201, version=location.version)


@router.patch("/locations/{location_id}", response_model=s.LocationOut)
@declare(access=LOCATION_MANAGE, read_only_ok=False)
async def update_location(
    location_id: UUID, body: s.UpdateName, version: IfMatch, uow: Uow, org: Org
) -> JSONResponse:
    location = await org.update_location(uow, location_id, expected_version=version, name=body.name)
    return _json(location_out(location), version=location.version)


@router.post("/locations/{location_id}/make-default", response_model=s.LocationOut)
@declare(access=LOCATION_MANAGE, read_only_ok=False)
async def make_default_location(location_id: UUID, uow: Uow, org: Org) -> JSONResponse:
    location = await org.make_default(uow, location_id)
    return _json(location_out(location), version=location.version)


@router.post("/locations/{location_id}/activate", response_model=s.LocationOut)
@declare(access=LOCATION_MANAGE, read_only_ok=False)
async def activate_location(location_id: UUID, uow: Uow, org: Org) -> JSONResponse:
    location = await org.change_location_status(uow, location_id, "active")
    return _json(location_out(location), version=location.version)


@router.post("/locations/{location_id}/deactivate", response_model=s.LocationOut)
@declare(access=LOCATION_MANAGE, read_only_ok=False)
async def deactivate_location(location_id: UUID, uow: Uow, org: Org) -> JSONResponse:
    location = await org.change_location_status(uow, location_id, "inactive")
    return _json(location_out(location), version=location.version)


# ------------------------------------------------------------------------------ departments
@router.get("/departments", response_model=s.DepartmentPage)
@declare(access=Authenticated(), read_only_ok=True)
async def list_departments(
    uow: Uow,
    after: After,
    limit: Limit,
    status: Annotated[Literal["active", "inactive"] | None, Query()] = None,
) -> JSONResponse:
    rows = await repository.list_departments(uow.db, status=status, after=after, limit=limit + 1)
    items, cursor = page(rows, limit, lambda row: row.id)
    return _json(s.DepartmentPage(items=[department_out(r) for r in items], next_cursor=cursor))


@router.get("/departments/{department_id}", response_model=s.DepartmentOut)
@declare(access=Authenticated(), read_only_ok=True)
async def get_department(department_id: UUID, uow: Uow, org: Org) -> JSONResponse:
    department = await org.get_department(uow, department_id)
    return _json(department_out(department), version=department.version)


@router.post("/departments", response_model=s.DepartmentOut, status_code=201)
@declare(access=DEPARTMENT_MANAGE, read_only_ok=False)
async def create_department(body: s.CreateDepartment, uow: Uow, org: Org) -> JSONResponse:
    department = await org.create_department(uow, code=body.code, name=body.name)
    return _json(department_out(department), status_code=201, version=department.version)


@router.patch("/departments/{department_id}", response_model=s.DepartmentOut)
@declare(access=DEPARTMENT_MANAGE, read_only_ok=False)
async def update_department(
    department_id: UUID, body: s.UpdateName, version: IfMatch, uow: Uow, org: Org
) -> JSONResponse:
    department = await org.update_department(uow, department_id, expected_version=version, name=body.name)
    return _json(department_out(department), version=department.version)


@router.post("/departments/{department_id}/activate", response_model=s.DepartmentOut)
@declare(access=DEPARTMENT_MANAGE, read_only_ok=False)
async def activate_department(department_id: UUID, uow: Uow, org: Org) -> JSONResponse:
    department = await org.change_department_status(uow, department_id, "active")
    return _json(department_out(department), version=department.version)


@router.post("/departments/{department_id}/deactivate", response_model=s.DepartmentOut)
@declare(access=DEPARTMENT_MANAGE, read_only_ok=False)
async def deactivate_department(department_id: UUID, uow: Uow, org: Org) -> JSONResponse:
    department = await org.change_department_status(uow, department_id, "inactive")
    return _json(department_out(department), version=department.version)
