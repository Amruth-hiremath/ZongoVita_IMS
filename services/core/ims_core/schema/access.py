"""Access classes of customer-database tables for the per-customer application role
(AD-62, AD-66, AD-67; LLD section 3, "Roles and grants", LD-06, LD-68).

Migrations grant privileges explicitly. This registry states what those grants must add up to,
and a database test compares it with the catalogue, so a table can never ship with rights it
should not have (in particular DELETE outside the exception list, or UPDATE on history).
"""

from __future__ import annotations

from enum import Enum

CUSTOMER_SCHEMAS: tuple[str, ...] = (
    "org",
    "iam",
    "catalog",
    "purchasing",
    "inventory",
    "ops",
    "workflow",
    "planning",
    "notify",
    "integration",
    "audit",
    "jobs",
    "config",
)


class AccessClass(Enum):
    #: SELECT, INSERT, UPDATE. No hard deletes (AD-67).
    BUSINESS = frozenset({"SELECT", "INSERT", "UPDATE"})
    #: INSERT and SELECT only; UPDATE and DELETE are also rejected by trigger (LD-06).
    APPEND_ONLY = frozenset({"SELECT", "INSERT"})
    #: Business rights plus DELETE: only for tables on the LLD's exception list.
    DELETABLE = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})


#: schema.table -> access class. Every table in the customer schemas must appear here.
TABLE_ACCESS: dict[str, AccessClass] = {
    "config.settings": AccessClass.BUSINESS,
    # Append-only for the application; partition retention is handled by the pipeline.
    "audit.audit_log": AccessClass.APPEND_ONLY,
    # Insert-only plus a column-level UPDATE of dispatch status (LD-67); see COLUMN_UPDATES.
    "integration.outbox_events": AccessClass.APPEND_ONLY,
    # Exception list: expired keys are deleted by the cleanup job.
    "integration.idempotency_keys": AccessClass.DELETABLE,
    # Identity (unit 2).
    "iam.users": AccessClass.BUSINESS,
    "iam.mfa_factors": AccessClass.BUSINESS,
    "iam.mfa_recovery_codes": AccessClass.BUSINESS,
    "iam.api_clients": AccessClass.BUSINESS,
    # Exception list: sessions past their absolute expiry are deleted by a cleanup job.
    "iam.sessions": AccessClass.DELETABLE,
}

#: Tables where UPDATE is granted on named columns only.
COLUMN_UPDATES: dict[str, frozenset[str]] = {
    "integration.outbox_events": frozenset({"status", "dispatched_at"}),
}

#: Tables that reject UPDATE and DELETE by trigger as well as by grant (LD-06).
TRIGGER_PROTECTED: frozenset[str] = frozenset({"audit.audit_log"})

#: The LLD's complete DELETE exception list (section 3). Tables join TABLE_ACCESS as DELETABLE
#: only if they are named here.
DELETE_EXCEPTION_LIST: frozenset[str] = frozenset(
    {
        "jobs.jobs",
        "jobs.periodic_runs",
        "integration.idempotency_keys",
        "iam.sessions",
        "iam.role_permissions",
        "catalog.taxonomy_synonyms",
        "catalog.item_barcodes",
    }
)
