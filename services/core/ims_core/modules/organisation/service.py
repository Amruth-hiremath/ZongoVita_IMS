"""Organisation use cases: sites, locations, departments and the licence site limit (LLD 5.1, 12;
AD-27, open item #30).

* A site is created staged or active, with its default location in the same transaction
  (exactly one default location per site). Staged and active sites count against the licence
  site limit: creating a site, or re-activating an inactive one, is refused at the limit
  (409 LIMIT_EXCEEDED) under a transaction-level advisory lock, as for users.
* Site transitions: staged -> active, staged -> inactive, active -> inactive, inactive -> active.
* The default location is active; another location becomes the default by command, which moves
  the flag in one transaction. The default cannot be deactivated.
* Codes are set at creation and identify records to integrations (the public API accepts
  location codes, LLD 12); names and the site timezone can be edited with If-Match.
* Nothing is deleted. Every change is audited in the same transaction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text

from ims_common.ids import uuid7
from ims_common.problem import DomainError
from ims_contracts.errors import ErrorCode, FieldError
from ims_core.kernel.uow import UnitOfWork
from ims_core.modules.organisation import repository
from ims_core.modules.organisation.repository import DepartmentRow, LocationRow, SiteRow

_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
SITE_LIMIT_LOCK = "SELECT pg_advisory_xact_lock(hashtext('org.licensed_sites'))"

#: Site status transitions (D-28). The database refuses any other.
SITE_TRANSITIONS: dict[str, frozenset[str]] = {
    "staged": frozenset({"active", "inactive"}),
    "active": frozenset({"inactive"}),
    "inactive": frozenset({"active"}),
}


def _invalid(field: str, message: str) -> DomainError:
    return DomainError(ErrorCode.VALIDATION_FAILED, errors=[FieldError(field=field, message=message)])


def _actor(uow: UnitOfWork) -> UUID | None:
    return uow.ctx.principal.id if uow.ctx.principal else None


def _name(value: str, field: str = "name") -> str:
    name = value.strip()
    if not name or len(name) > 200:
        raise _invalid(field, "is required and at most 200 characters")
    return name


def _code(value: str, field: str = "code") -> str:
    code = value.strip()
    if not _CODE.fullmatch(code):
        raise _invalid(field, "1 to 32 letters, digits, '.', '_' or '-', starting with a letter or digit")
    return code


_KNOWN_TIMEZONE = text("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_timezone_names WHERE name = :zone)")


async def _timezone(uow: UnitOfWork, value: str) -> str:
    """An IANA name the customer's PostgreSQL knows: daily jobs and site-time display convert
    with it (LLD 3). PostgreSQL decides, because its time-zone data can differ from Python's
    (finding F-05: Python accepts the legacy alias Asia/Calcutta, this PostgreSQL does not)."""
    zone = value.strip()
    if not zone or not (await uow.db.execute(_KNOWN_TIMEZONE, {"zone": zone})).scalar_one():
        raise _invalid("timezone", "must be an IANA timezone such as Asia/Kolkata")
    return zone


@dataclass(frozen=True)
class LocationSeed:
    code: str
    name: str


class OrganisationService:
    # ------------------------------------------------------------------------------ helpers
    @staticmethod
    async def _require_free(uow: UnitOfWork, table: str, code: str, field: str = "code") -> None:
        if await repository.code_taken(uow.db, table, code):
            raise _invalid(field, "is already in use")

    @staticmethod
    async def _check_site_limit(uow: UnitOfWork) -> None:
        """AD-27, #30: creation or activation is refused at the licence site limit."""
        await uow.db.execute(text(SITE_LIMIT_LOCK))
        if await repository.count_licensed_sites(uow.db) >= uow.ctx.snapshot.max_sites:
            raise DomainError(ErrorCode.LIMIT_EXCEEDED, "the licence site limit has been reached")

    # -------------------------------------------------------------------------------- sites
    @staticmethod
    async def get_site(uow: UnitOfWork, site_id: UUID) -> SiteRow:
        site = await repository.read_site(uow.db, site_id)
        if site is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        return site

    async def create_site(
        self,
        uow: UnitOfWork,
        *,
        code: str,
        name: str,
        timezone: str,
        status: str,
        default_location: LocationSeed,
    ) -> tuple[SiteRow, LocationRow]:
        code, name, zone = _code(code), _name(name), await _timezone(uow, timezone)
        if status not in ("staged", "active"):
            raise _invalid("status", "a new site is staged or active")
        location_code = _code(default_location.code, "default_location.code")
        location_name = _name(default_location.name, "default_location.name")
        await self._require_free(uow, "org.sites", code)
        await self._require_free(uow, "org.locations", location_code, "default_location.code")
        await self._check_site_limit(uow)

        site_id, location_id = uuid7(), uuid7()
        actor = _actor(uow)
        await repository.insert_site(
            uow.db, site_id=site_id, code=code, name=name, timezone=zone, status=status, actor=actor
        )
        await repository.insert_location(
            uow.db,
            location_id=location_id,
            site_id=site_id,
            code=location_code,
            name=location_name,
            is_default=True,
            actor=actor,
        )
        await uow.audit.record(
            action="org.site.created",
            entity_type="org.site",
            entity_id=site_id,
            site_id=site_id,
            after={"code": code, "name": name, "timezone": zone, "status": status},
        )
        await uow.audit.record(
            action="org.location.created",
            entity_type="org.location",
            entity_id=location_id,
            site_id=site_id,
            after={"code": location_code, "name": location_name, "is_default": True, "status": "active"},
        )
        site = await repository.read_site(uow.db, site_id)
        location = await repository.read_location(uow.db, location_id)
        assert site is not None and location is not None
        return site, location

    async def update_site(
        self, uow: UnitOfWork, site_id: UUID, *, expected_version: int, name: str, timezone: str
    ) -> SiteRow:
        site = await repository.read_site(uow.db, site_id, lock=True)
        if site is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        if site.version != expected_version:
            raise DomainError(ErrorCode.VERSION_CONFLICT)
        after = {"name": _name(name), "timezone": await _timezone(uow, timezone)}
        before = {"name": site.name, "timezone": site.timezone}
        if after != before:
            await repository.update_site(uow.db, site_id, actor=_actor(uow), **after)
            await uow.audit.record(
                action="org.site.updated",
                entity_type="org.site",
                entity_id=site_id,
                site_id=site_id,
                before=before,
                after=after,
            )
        return await self.get_site(uow, site_id)

    async def change_site_status(self, uow: UnitOfWork, site_id: UUID, target: str) -> SiteRow:
        site = await repository.read_site(uow.db, site_id, lock=True)
        if site is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        if target not in SITE_TRANSITIONS[site.status]:
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION, f"a {site.status} site cannot become {target}"
            )
        if site.status == "inactive":
            # Back to counting against the licence (AD-27: "checked at creation or activation").
            await self._check_site_limit(uow)
        await repository.update_site(uow.db, site_id, actor=_actor(uow), status=target)
        await uow.audit.record(
            action="org.site.activated" if target == "active" else "org.site.deactivated",
            entity_type="org.site",
            entity_id=site_id,
            site_id=site_id,
            before={"status": site.status},
            after={"status": target},
        )
        return await self.get_site(uow, site_id)

    # ---------------------------------------------------------------------------- locations
    @staticmethod
    async def get_location(uow: UnitOfWork, location_id: UUID) -> LocationRow:
        location = await repository.read_location(uow.db, location_id)
        if location is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        return location

    async def create_location(self, uow: UnitOfWork, *, site_id: UUID, code: str, name: str) -> LocationRow:
        code, name = _code(code), _name(name)
        if await repository.read_site(uow.db, site_id) is None:
            raise _invalid("site_id", "no such site")
        await self._require_free(uow, "org.locations", code)
        location_id = uuid7()
        await repository.insert_location(
            uow.db,
            location_id=location_id,
            site_id=site_id,
            code=code,
            name=name,
            is_default=False,
            actor=_actor(uow),
        )
        await uow.audit.record(
            action="org.location.created",
            entity_type="org.location",
            entity_id=location_id,
            site_id=site_id,
            after={"code": code, "name": name, "is_default": False, "status": "active"},
        )
        return await self.get_location(uow, location_id)

    async def update_location(
        self, uow: UnitOfWork, location_id: UUID, *, expected_version: int, name: str
    ) -> LocationRow:
        location = await repository.read_location(uow.db, location_id, lock=True)
        if location is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        if location.version != expected_version:
            raise DomainError(ErrorCode.VERSION_CONFLICT)
        name = _name(name)
        if name != location.name:
            await repository.update_location(uow.db, location_id, actor=_actor(uow), name=name)
            await uow.audit.record(
                action="org.location.updated",
                entity_type="org.location",
                entity_id=location_id,
                site_id=location.site_id,
                before={"name": location.name},
                after={"name": name},
            )
        return await self.get_location(uow, location_id)

    async def make_default(self, uow: UnitOfWork, location_id: UUID) -> LocationRow:
        """Move the site's default to this location in one transaction (LLD 5.1)."""
        location = await repository.read_location(uow.db, location_id, lock=True)
        if location is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        if location.is_default:
            return location
        if location.status != "active":
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION, "an inactive location cannot be the default"
            )
        previous = await repository.lock_default_location(uow.db, location.site_id)
        actor = _actor(uow)
        if previous is not None:
            await repository.update_location(uow.db, previous.id, actor=actor, is_default=False)
        await repository.update_location(uow.db, location_id, actor=actor, is_default=True)
        await uow.audit.record(
            action="org.location.default_changed",
            entity_type="org.location",
            entity_id=location_id,
            site_id=location.site_id,
            before={"default_location_id": previous.id if previous else None},
            after={"default_location_id": location_id},
        )
        return await self.get_location(uow, location_id)

    async def change_location_status(self, uow: UnitOfWork, location_id: UUID, target: str) -> LocationRow:
        location = await repository.read_location(uow.db, location_id, lock=True)
        if location is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        if location.status == target:
            raise DomainError(ErrorCode.INVALID_STATE_TRANSITION, f"the location is already {target}")
        if target == "inactive" and location.is_default:
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION,
                "make another location the default before deactivating this one",
            )
        await repository.update_location(uow.db, location_id, actor=_actor(uow), status=target)
        await uow.audit.record(
            action="org.location.activated" if target == "active" else "org.location.deactivated",
            entity_type="org.location",
            entity_id=location_id,
            site_id=location.site_id,
            before={"status": location.status},
            after={"status": target},
        )
        return await self.get_location(uow, location_id)

    # -------------------------------------------------------------------------- departments
    @staticmethod
    async def get_department(uow: UnitOfWork, department_id: UUID) -> DepartmentRow:
        department = await repository.read_department(uow.db, department_id)
        if department is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        return department

    async def create_department(self, uow: UnitOfWork, *, code: str, name: str) -> DepartmentRow:
        code, name = _code(code), _name(name)
        await self._require_free(uow, "org.departments", code)
        department_id = uuid7()
        await repository.insert_department(
            uow.db, department_id=department_id, code=code, name=name, actor=_actor(uow)
        )
        await uow.audit.record(
            action="org.department.created",
            entity_type="org.department",
            entity_id=department_id,
            after={"code": code, "name": name, "status": "active"},
        )
        return await self.get_department(uow, department_id)

    async def update_department(
        self, uow: UnitOfWork, department_id: UUID, *, expected_version: int, name: str
    ) -> DepartmentRow:
        department = await repository.read_department(uow.db, department_id, lock=True)
        if department is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        if department.version != expected_version:
            raise DomainError(ErrorCode.VERSION_CONFLICT)
        name = _name(name)
        if name != department.name:
            await repository.update_department(uow.db, department_id, actor=_actor(uow), name=name)
            await uow.audit.record(
                action="org.department.updated",
                entity_type="org.department",
                entity_id=department_id,
                before={"name": department.name},
                after={"name": name},
            )
        return await self.get_department(uow, department_id)

    async def change_department_status(
        self, uow: UnitOfWork, department_id: UUID, target: str
    ) -> DepartmentRow:
        department = await repository.read_department(uow.db, department_id, lock=True)
        if department is None:
            raise DomainError(ErrorCode.NOT_FOUND)
        if department.status == target:
            raise DomainError(ErrorCode.INVALID_STATE_TRANSITION, f"the department is already {target}")
        await repository.update_department(uow.db, department_id, actor=_actor(uow), status=target)
        await uow.audit.record(
            action="org.department.activated" if target == "active" else "org.department.deactivated",
            entity_type="org.department",
            entity_id=department_id,
            before={"status": department.status},
            after={"status": target},
        )
        return await self.get_department(uow, department_id)
