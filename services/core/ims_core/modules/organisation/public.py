"""What other modules may use from the organisation module (LD-01)."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from ims_core.kernel.uow import UnitOfWork
from ims_core.modules.organisation import repository
from ims_core.modules.organisation.repository import DepartmentRow, SiteRow

__all__ = ["DepartmentRow", "SiteRow", "active_sites", "read_department", "read_site", "sites_by_id"]


async def read_site(uow: UnitOfWork, site_id: UUID) -> SiteRow | None:
    return await repository.read_site(uow.db, site_id)


async def sites_by_id(uow: UnitOfWork, site_ids: Iterable[UUID]) -> dict[UUID, SiteRow]:
    return await repository.sites_by_id(uow.db, site_ids)


async def active_sites(uow: UnitOfWork) -> list[SiteRow]:
    """Active sites in code order: where stock is held and work happens."""
    return await repository.active_sites(uow.db)


async def read_department(uow: UnitOfWork, department_id: UUID) -> DepartmentRow | None:
    return await repository.read_department(uow.db, department_id)
