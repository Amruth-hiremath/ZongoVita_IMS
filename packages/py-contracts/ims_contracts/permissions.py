"""Permission catalogue and seeded roles (LLD 5.1, section 7; AD-45, AD-46).

The catalogue is code-defined: every migration rebuilds ``iam.permission_catalog`` from
``CATALOGUE`` (database pipeline), and the web app's ``packages/api-client/src/permissions.ts``
must list exactly the same codes, scopes and seeded roles (a static test compares them).

Seeded roles are written once, at provisioning, by natural-key upsert (LLD 6.6). After that the
customer may edit every seeded role except Super Admin (#10), so later releases never overwrite
their permissions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class PermissionDef:
    code: str
    site_scoped: bool
    reserved_to_super_admin: bool = False

    @property
    def module(self) -> str:
        """First segment of module.resource.action."""
        return self.code.split(".", 1)[0]

    @property
    def action(self) -> str:
        return self.code.rsplit(".", 1)[1]

    @property
    def is_view(self) -> bool:
        return self.action in ("view", "view_all")


def _p(code: str, *, site: bool = False, reserved: bool = False) -> PermissionDef:
    return PermissionDef(code, site_scoped=site, reserved_to_super_admin=reserved)


#: LLD section 7, in the LLD's order. ``site=True`` marks the permissions starred there.
CATALOGUE: tuple[PermissionDef, ...] = (
    # Catalogue
    _p("catalog.item.view"),
    _p("catalog.item.create"),
    _p("catalog.item.edit"),
    _p("catalog.item.approve"),
    _p("catalog.item.deactivate"),
    _p("catalog.taxonomy.propose"),
    _p("catalog.taxonomy.approve"),
    _p("catalog.attribute.manage"),
    _p("catalog.numbering.manage"),
    _p("catalog.asset.manage", site=True),
    # Inventory, receiving
    _p("inventory.stock.view", site=True),
    _p("inventory.ledger.view", site=True),
    _p("receiving.grn.create", site=True),
    _p("receiving.grn.inspect", site=True),
    _p("receiving.grn.post", site=True),
    # Issuance, transfers, counts
    _p("issuance.request.create", site=True),
    _p("issuance.request.view_all", site=True),
    _p("issuance.request.approve", site=True),
    _p("issuance.issue.fulfil", site=True),
    _p("transfers.transfer.create", site=True),
    _p("transfers.transfer.approve", site=True),
    _p("transfers.transfer.dispatch", site=True),
    _p("transfers.transfer.receive", site=True),
    _p("counts.session.manage", site=True),
    _p("counts.session.count", site=True),
    _p("counts.adjustment.approve", site=True),
    # Returns and quality
    _p("returns.return.create", site=True),
    _p("returns.return.receive", site=True),
    _p("returns.return.validate", site=True),
    _p("returns.verdict.decide", site=True),
    _p("quality.case.dispose", site=True),
    _p("quality.register.view"),
    # Purchasing, replenishment
    _p("purchasing.vendor.view"),
    _p("purchasing.vendor.manage"),
    _p("purchasing.vendor.approve"),
    _p("purchasing.record.view"),
    _p("purchasing.record.manage"),
    _p("replenishment.planning.view", site=True),
    _p("replenishment.planning.edit", site=True),
    _p("replenishment.threshold.approve", site=True),
    _p("replenishment.formula.manage"),
    # Workflow, access, organisation
    _p("workflow.policy.manage"),
    _p("workflow.task.view"),
    _p("access.user.manage"),
    _p("access.role.manage"),
    _p("access.api_client.manage"),
    _p("access.super_admin.transfer", reserved=True),
    _p("access.support.grant", reserved=True),
    _p("access.recovery_approver.manage", reserved=True),
    _p("org.site.manage"),
    _p("org.location.manage"),
    _p("org.department.manage"),
    # Alerts, reporting, audit, integration, settings
    _p("alerts.alert.view", site=True),
    _p("alerts.alert.manage", site=True),
    _p("reporting.report.view", site=True),
    _p("reporting.export.run", site=True),
    _p("audit.log.view", site=True),
    _p("integration.webhook.manage"),
    _p("integration.connector.manage"),
    _p("integration.mapping.manage"),
    _p("integration.sync.view"),
    _p("config.settings.manage"),
)

PERMISSIONS: dict[str, PermissionDef] = {p.code: p for p in CATALOGUE}
ALL_CODES: frozenset[str] = frozenset(PERMISSIONS)
RESERVED_TO_SUPER_ADMIN: frozenset[str] = frozenset(p.code for p in CATALOGUE if p.reserved_to_super_admin)
#: Permissions that administer access itself. Support principals never hold them (LLD section 7).
ACCESS_PERMISSIONS: frozenset[str] = frozenset(p.code for p in CATALOGUE if p.module == "access")
VIEW_PERMISSIONS: frozenset[str] = frozenset(p.code for p in CATALOGUE if p.is_view)


class RoleKind(StrEnum):
    """iam.roles.kind (LLD 5.1)."""

    USER_TYPE = "user_type"
    SUPER_ADMIN = "super_admin"
    CUSTOM = "custom"


@dataclass(frozen=True)
class SeededRole:
    code: str
    name: str
    kind: RoleKind
    user_type_no: int | None
    permissions: frozenset[str]

    @property
    def is_super_admin(self) -> bool:
        return self.kind is RoleKind.SUPER_ADMIN


SUPER_ADMIN_ROLE_CODE = "super_admin"

# LLD 5.1, "Seeded roles". Where a phrase covers several permissions, the reading is recorded in
# Docs/Implementation_Progress.md (decision I-26).
_TYPE_2 = VIEW_PERMISSIONS | {
    # approve issuance, transfers, adjustments, verdicts, categories, thresholds
    "issuance.request.approve",
    "transfers.transfer.approve",
    "counts.adjustment.approve",
    "returns.verdict.decide",
    "catalog.taxonomy.approve",
    "replenishment.threshold.approve",
    # manage vendors and formulas
    "purchasing.vendor.manage",
    "replenishment.formula.manage",
}
_TYPE_3 = frozenset(
    {
        # view stock (the item master is what stock is read against)
        "inventory.stock.view",
        "catalog.item.view",
        # receive
        "receiving.grn.create",
        "receiving.grn.inspect",
        "receiving.grn.post",
        # issue (also emergency issue)
        "issuance.issue.fulfil",
        # transfer
        "transfers.transfer.create",
        "transfers.transfer.dispatch",
        "transfers.transfer.receive",
        # count
        "counts.session.count",
        # validate returns (taking returned units in comes first)
        "returns.return.receive",
        "returns.return.validate",
        # raise requests
        "issuance.request.create",
    }
)
_TYPE_4 = frozenset(
    {
        # raise requests and returns; acknowledging and viewing their own records needs no
        # permission (requester-only routes, LLD 12)
        "issuance.request.create",
        "returns.return.create",
    }
)

SEEDED_ROLES: tuple[SeededRole, ...] = (
    # Holds every permission by definition; never stored as role_permissions rows (I-25).
    SeededRole(SUPER_ADMIN_ROLE_CODE, "Super Admin", RoleKind.SUPER_ADMIN, None, ALL_CODES),
    SeededRole("user_type_1", "User Type 1", RoleKind.USER_TYPE, 1, ALL_CODES - RESERVED_TO_SUPER_ADMIN),
    SeededRole("user_type_2", "User Type 2", RoleKind.USER_TYPE, 2, frozenset(_TYPE_2)),
    SeededRole("user_type_3", "User Type 3", RoleKind.USER_TYPE, 3, _TYPE_3),
    SeededRole("user_type_4", "User Type 4", RoleKind.USER_TYPE, 4, _TYPE_4),
)
SEEDED_BY_CODE: dict[str, SeededRole] = {role.code: role for role in SEEDED_ROLES}


def _check() -> None:
    for role in SEEDED_ROLES:
        unknown = role.permissions - ALL_CODES
        if unknown:
            raise AssertionError(f"{role.code}: unknown permissions {sorted(unknown)}")
        if not role.is_super_admin and role.permissions & RESERVED_TO_SUPER_ADMIN:
            raise AssertionError(f"{role.code} holds a reserved permission")


_check()
