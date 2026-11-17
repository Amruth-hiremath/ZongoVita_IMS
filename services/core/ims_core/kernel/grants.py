"""Effective permissions of the acting principal (LLD section 7, "Evaluation").

Computed by the access module at pipeline step 8 and placed on the unit of work, so handlers can
apply site scope to what they load:

* a command on a record checks the record's own site, never a request parameter:
  ``uow.grants.require_site("transfers.transfer.dispatch", transfer.from_site_id)``;
* a list filters in SQL with ``site_id = ANY(:sites)`` using ``uow.grants.sites(code)``, where
  ``None`` means every site (no filter);
* a record outside the caller's sites is reported as 404 NOT_FOUND when it is read (LLD 12), and
  as 403 SITE_SCOPE_DENIED when the caller can see it but may not act on it at that site.

The kernel holds only this data structure; how it is computed (roles, assignments, the super
admin, support grants) belongs to the access module.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID

from ims_common.problem import DomainError
from ims_contracts.errors import ErrorCode

#: Sites at which a permission is held: ``None`` for every site.
SiteScope = frozenset[UUID] | None


@dataclass(frozen=True)
class Grants:
    """Permission code -> sites. Non-site-scoped permissions always map to ``None``."""

    by_code: Mapping[str, SiteScope] = field(default_factory=dict)
    is_super_admin: bool = False

    def holds(self, code: str) -> bool:
        """Held at one site at least (the route-level check of step 8)."""
        return code in self.by_code

    def sites(self, code: str) -> SiteScope:
        """Sites for a list filter; ``None`` is every site. Not held at all: the empty set."""
        if code not in self.by_code:
            return frozenset()
        return self.by_code[code]

    def holds_at(self, code: str, site_id: UUID | None) -> bool:
        if code not in self.by_code:
            return False
        scope = self.by_code[code]
        if scope is None:
            return True
        return site_id is not None and site_id in scope

    def require(self, code: str) -> None:
        if not self.holds(code):
            raise DomainError(ErrorCode.PERMISSION_DENIED)

    def require_site(self, code: str, site_id: UUID | None) -> None:
        """For a command on a loaded record: the permission must be held at the record's site."""
        if not self.holds(code):
            raise DomainError(ErrorCode.PERMISSION_DENIED)
        if not self.holds_at(code, site_id):
            raise DomainError(ErrorCode.SITE_SCOPE_DENIED)

    def can_see_site(self, code: str, site_id: UUID | None) -> bool:
        """For a read of a loaded record: outside the caller's sites it does not exist (404)."""
        return self.holds_at(code, site_id)


NO_GRANTS = Grants()
