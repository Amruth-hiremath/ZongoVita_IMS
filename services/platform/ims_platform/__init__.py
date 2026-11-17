"""ZongoVita Platform Service.

Owns the Licence Registry and licence state machine, the Login Directory, provisioning control
and snapshot bundles (AD-11). Built as the future shared ZongoVita platform service behind a
narrow, product-neutral interface (AD-12). Holds no credential that reads customer business
data and no DDL credential (AD-13).
"""

from pathlib import Path


def migrations_path() -> Path:
    """Location of the Control-Plane migrations, for the database pipeline."""
    return Path(__file__).resolve().parent.parent / "migrations"
