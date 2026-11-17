"""Helpers for writing migrations as plain SQL."""

from __future__ import annotations

from collections.abc import Iterable

import sqlalchemy as sa
from alembic import op


def execute_statements(statements: Iterable[str]) -> None:
    """Run literal SQL statements in order.

    Every colon is escaped so SQLAlchemy never mistakes ``:name`` inside DDL (regular
    expressions, JSON defaults, PL/pgSQL) for a bind parameter. Percent signs are handled by
    SQLAlchemy itself. Statements therefore run exactly as written.
    """
    bind = op.get_bind()
    for statement in statements:
        bind.execute(sa.text(statement.replace(":", r"\:")))


def quote_ident(name: str) -> str:
    """Quote an identifier for interpolation into DDL (role and database names)."""
    if "\x00" in name:
        raise ValueError("identifier contains a NUL byte")
    return '"' + name.replace('"', '""') + '"'
