"""Permission catalogue rebuild and seeded roles (LLD 5.1, 6.6).

Runs as the customer's migration role in the migration's own transaction, after every upgrade:

- ``iam.permission_catalog`` is made equal to ``ims_contracts.permissions.CATALOGUE`` ("rebuilt
  from code by every migration"). A code that disappears from the catalogue, or becomes reserved
  to the Super Admin, is first removed from every role, with an audit entry per removal.
- The seeded roles (Super Admin, User Types 1 to 4) are inserted by natural key if missing, with
  their default permissions. Existing roles are never changed: customers may edit every seeded
  role except Super Admin (#10), and a later release must not undo that.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import Connection, text

from ims_common.ids import uuid7
from ims_contracts.permissions import CATALOGUE, SEEDED_ROLES

PIPELINE_REQUEST_ID = "pipeline:access-seed"


@dataclass
class AccessSeedReport:
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    revoked_from_roles: list[tuple[str, str]] = field(default_factory=list)
    roles_created: list[str] = field(default_factory=list)

    @property
    def unchanged(self) -> bool:
        return not (
            self.added or self.changed or self.removed or self.revoked_from_roles or self.roles_created
        )


def _audit_removal(
    connection: Connection, role_id: object, role_code: str, permission: str, why: str
) -> None:
    connection.execute(
        text(
            "INSERT INTO audit.audit_log (actor_type, action, entity_type, entity_id, before, after, "
            "reason, request_id, source) VALUES ('system', 'iam.role.permissions_changed', 'iam.role', "
            ":role_id, CAST(:before AS jsonb), CAST(:after AS jsonb), :reason, :request_id, 'system')"
        ),
        {
            "role_id": str(role_id),
            "before": json.dumps({"code": role_code, "permission": permission, "granted": True}),
            "after": json.dumps({"code": role_code, "permission": permission, "granted": False}),
            "reason": why,
            "request_id": PIPELINE_REQUEST_ID,
        },
    )


def _revoke_everywhere(connection: Connection, codes: list[str], why: str, report: AccessSeedReport) -> None:
    if not codes:
        return
    rows = connection.execute(
        text(
            "DELETE FROM iam.role_permissions rp USING iam.roles r "
            "WHERE r.id = rp.role_id AND rp.permission_code = ANY(:codes) "
            "RETURNING rp.role_id, r.code, rp.permission_code"
        ),
        {"codes": codes},
    ).all()
    for role_id, role_code, permission in rows:
        _audit_removal(connection, role_id, role_code, permission, why)
        report.revoked_from_roles.append((role_code, permission))


def sync_permission_catalog(connection: Connection, report: AccessSeedReport) -> None:
    existing = {
        row.code: (row.site_scoped, row.reserved_to_super_admin)
        for row in connection.execute(
            text("SELECT code, site_scoped, reserved_to_super_admin FROM iam.permission_catalog")
        )
    }
    wanted = {p.code: p for p in CATALOGUE}

    stale = sorted(set(existing) - set(wanted))
    newly_reserved = sorted(
        code
        for code, p in wanted.items()
        if p.reserved_to_super_admin and code in existing and not existing[code][1]
    )
    _revoke_everywhere(connection, stale, "permission removed from the catalogue by a release", report)
    _revoke_everywhere(
        connection, newly_reserved, "permission reserved to the Super Admin by a release", report
    )
    if stale:
        connection.execute(
            text("DELETE FROM iam.permission_catalog WHERE code = ANY(:codes)"), {"codes": stale}
        )
        report.removed.extend(stale)

    for code, permission in wanted.items():
        current = existing.get(code)
        target = (permission.site_scoped, permission.reserved_to_super_admin)
        if current == target:
            continue
        connection.execute(
            text(
                "INSERT INTO iam.permission_catalog (code, module, site_scoped, reserved_to_super_admin) "
                "VALUES (:code, :module, :site_scoped, :reserved) "
                "ON CONFLICT (code) DO UPDATE SET site_scoped = EXCLUDED.site_scoped, "
                "reserved_to_super_admin = EXCLUDED.reserved_to_super_admin"
            ),
            {
                "code": code,
                "module": permission.module,
                "site_scoped": permission.site_scoped,
                "reserved": permission.reserved_to_super_admin,
            },
        )
        (report.added if current is None else report.changed).append(code)


def seed_roles(connection: Connection, report: AccessSeedReport) -> None:
    for role in SEEDED_ROLES:
        role_id = connection.execute(
            text(
                "INSERT INTO iam.roles (id, code, name, kind, user_type_no, is_super_admin_equivalent) "
                "VALUES (:id, :code, :name, :kind, :user_type_no, :super_admin) "
                "ON CONFLICT (code) DO NOTHING RETURNING id"
            ),
            {
                "id": uuid7(),
                "code": role.code,
                "name": role.name,
                "kind": role.kind.value,
                "user_type_no": role.user_type_no,
                "super_admin": role.is_super_admin,
            },
        ).scalar_one_or_none()
        if role_id is None:
            continue
        report.roles_created.append(role.code)
        if role.is_super_admin:
            continue  # holds every permission by definition (decision I-25)
        connection.execute(
            text("INSERT INTO iam.role_permissions (role_id, permission_code) VALUES (:role_id, :code)"),
            [{"role_id": role_id, "code": code} for code in sorted(role.permissions)],
        )


def seed_access(connection: Connection) -> AccessSeedReport:
    report = AccessSeedReport()
    sync_permission_catalog(connection, report)
    seed_roles(connection, report)
    return report
