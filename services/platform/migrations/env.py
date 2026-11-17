"""Alembic environment for the Control-Plane database.

Migrations run only from the database pipeline (AD-13, AD-29), which opens the connection as
``platform_migrator`` and hands it in. There is deliberately no URL-based or offline mode.
"""

from alembic import context

config = context.config
connection = config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Control-Plane migrations run only through pipelines/database")

context.configure(connection=connection, target_metadata=None, transactional_ddl=True)
with context.begin_transaction():
    context.run_migrations()
