"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""

from ims_common.ddl import execute_statements
from ims_core.schema.ddl import app_role

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    raise NotImplementedError("migrations only expand (LLD 6.7); roll forward instead")
