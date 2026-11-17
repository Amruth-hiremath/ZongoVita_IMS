"""Alembic environment for customer databases.

Migrations run only from the database pipeline under the per-customer migration role (AD-29,
LD-85). The pipeline opens the connection and passes it in together with the names of this
customer's roles, which the grants in each revision need. There is no URL-based or offline mode.
"""

from alembic import context

config = context.config
connection = config.attributes.get("connection")
if connection is None:
    raise RuntimeError("customer-database migrations run only through pipelines/database")
for required in ("app_role", "breakglass_role"):
    if not config.attributes.get(required):
        raise RuntimeError(f"pipeline did not supply {required}")

context.configure(connection=connection, target_metadata=None, transactional_ddl=True)
with context.begin_transaction():
    context.run_migrations()
