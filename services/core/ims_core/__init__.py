"""ZongoVita IMS Core: a modular monolith (AD-01).

``kernel`` holds everything every request and job passes through (tenant context, licence state
gate, database routing, authentication, unit of work, audit, outbox, idempotency).
``modules`` holds one package per business module. ``schema`` describes the customer database
for the pipeline and for verification.
"""

from pathlib import Path


def migrations_path() -> Path:
    """Location of the customer-database migrations, for the database pipeline."""
    return Path(__file__).resolve().parent.parent / "migrations"
