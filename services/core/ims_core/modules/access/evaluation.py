"""Effective permissions (LLD section 7, "Evaluation" and "Caching").

Effective permissions are the union over the principal's active role assignments, each with its
site (null = all sites). The super admin holds every permission at every site. A permission that
is not site-scoped is held everywhere as soon as any assignment carries it.

Results are cached per process, keyed by (customer, principal, access_version), for up to 60
seconds (LLD 16). Every role, permission or assignment change increments iam.access_version in
the same transaction (trigger), so a changed principal is never served from a stale entry once
the change has committed. The cache holds no state that matters: losing it costs one query.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from ims_contracts.permissions import ALL_CODES, PERMISSIONS
from ims_core.kernel.grants import Grants, SiteScope

SUPER_ADMIN_GRANTS = Grants(by_code=dict.fromkeys(sorted(ALL_CODES)), is_super_admin=True)


def grants_from(rows: Iterable[tuple[UUID | None, str | None]], *, super_admin: bool) -> Grants:
    """``rows`` are (assignment site, permission code) pairs; site ``None`` is every site."""
    if super_admin:
        return SUPER_ADMIN_GRANTS
    every_site: set[str] = set()
    some_sites: dict[str, set[UUID]] = {}
    for site_id, code in rows:
        definition = PERMISSIONS.get(code) if code else None
        if definition is None:
            continue  # catalogue rows unknown to this release (rolling deployment) grant nothing
        if site_id is None or not definition.site_scoped:
            every_site.add(code)  # type: ignore[arg-type]
        else:
            some_sites.setdefault(definition.code, set()).add(site_id)
    by_code: dict[str, SiteScope] = dict.fromkeys(sorted(every_site))
    for code, sites in sorted(some_sites.items()):
        if code not in by_code:
            by_code[code] = frozenset(sites)
    return Grants(by_code=by_code)


@dataclass(frozen=True)
class _Key:
    customer_id: UUID
    principal_type: str
    principal_id: UUID
    access_version: int


class PermissionCache:
    """Bounded per-process cache of effective permissions."""

    def __init__(self, *, ttl_seconds: float = 60.0, max_entries: int = 20_000) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._entries: OrderedDict[_Key, tuple[Grants, float]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(
        self, customer_id: UUID, principal_type: str, principal_id: UUID, version: int, now: float
    ) -> Grants | None:
        key = _Key(customer_id, principal_type, principal_id, version)
        entry = self._entries.get(key)
        if entry is None or now - entry[1] >= self._ttl:
            if entry is not None:
                del self._entries[key]
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        return entry[0]

    def put(
        self,
        customer_id: UUID,
        principal_type: str,
        principal_id: UUID,
        version: int,
        now: float,
        grants: Grants,
    ) -> None:
        key = _Key(customer_id, principal_type, principal_id, version)
        self._entries[key] = (grants, now)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()
