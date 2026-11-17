"""Login Directory: lookup hash and one entry per principal (LLD 4, 6.3; AD-79).

``lookup_hash`` is the identifier hashed with the directory lookup key, which products hold so
that they can resolve an identifier from the signed snapshot bundle during a Platform Service
outage. The pepper-keyed ``login_hash`` stays the directory's key and the pepper stays inside the
Platform Service (LD-10). Nullable at the database level because a migration cannot compute it for
existing rows (only hashes are stored); the directory service always writes it.

Revision ID: 0002
Revises: 0001
"""

from ims_common.ddl import execute_statements

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

STATEMENTS = [
    "ALTER TABLE platform.login_directory ADD COLUMN lookup_hash bytea",
    """
    ALTER TABLE platform.login_directory
        ADD CONSTRAINT login_directory_lookup_hash_length
        CHECK (lookup_hash IS NULL OR octet_length(lookup_hash) = 32) NOT VALID
    """,
    "ALTER TABLE platform.login_directory VALIDATE CONSTRAINT login_directory_lookup_hash_length",
    "CREATE UNIQUE INDEX login_directory_lookup_hash_key ON platform.login_directory (lookup_hash)",
    # A principal signs in with exactly one identifier.
    """
    CREATE UNIQUE INDEX login_directory_one_entry_per_principal
        ON platform.login_directory (customer_id, principal_type, principal_id)
    """,
    # The directory is never cleaned row by row: entries are disabled, not deleted.
    """
    CREATE TRIGGER login_directory_no_delete BEFORE DELETE ON platform.login_directory
        FOR EACH ROW EXECUTE FUNCTION platform.reject_change()
    """,
]


def upgrade() -> None:
    execute_statements(STATEMENTS)


def downgrade() -> None:
    raise NotImplementedError("migrations only expand (LLD 6.7); roll forward instead")
