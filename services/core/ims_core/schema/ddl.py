"""Helpers used inside customer-database migrations."""

from __future__ import annotations

from alembic import context

from ims_common.ddl import quote_ident


def app_role() -> str:
    """Quoted name of this customer's application role (ims_app_<customer>)."""
    return quote_ident(context.config.attributes["app_role"])


def breakglass_role() -> str:
    """Quoted name of this customer's break-glass role (ims_breakglass_<customer>)."""
    return quote_ident(context.config.attributes["breakglass_role"])


def append_only_triggers(schema: str, table: str) -> list[str]:
    """Statements that make a table reject UPDATE, DELETE and TRUNCATE (LD-06)."""
    return [
        f"""
        CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {schema}.{table}
            FOR EACH ROW EXECUTE FUNCTION audit.reject_change()
        """,
        f"""
        CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {schema}.{table}
            FOR EACH STATEMENT EXECUTE FUNCTION audit.reject_change()
        """,
    ]
