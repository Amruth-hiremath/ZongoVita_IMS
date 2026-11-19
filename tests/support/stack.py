"""The test stack: a dedicated PostgreSQL + PgBouncer pair (deploy/local, project ims-test).

Every run starts from an empty cluster: all IMS databases and roles are dropped and the
Control-Plane database is provisioned and migrated again through the real pipeline. That wipe
is only ever performed on a cluster that identifies itself as the test cluster.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from ims_common.credentials import SecretBox
from ims_common.identifiers import new_key_secret
from ims_common.objectstore import FileObjectStore
from ims_common.pg import create_pooler_engine
from ims_common.secrets import FileSecretsStore
from ims_common.tokens import KeySet
from ims_contracts.enums import DatabaseStatus, LicenceModule, Placement
from ims_core.kernel.runtime import CORE_READABLE_SECRETS
from ims_db_pipeline.cluster import ClusterAdmin, cluster_admin_ref
from ims_db_pipeline.migrate import migrate_control_plane, migrate_customer_database
from ims_db_pipeline.provision import CustomerDatabase, provision_control_plane, provision_customer_database
from ims_platform.registry import Actor, RegistryService
from ims_platform.runtime import PLATFORM_READABLE_SECRETS

PG_HOST = os.environ.get("IMS_TEST_PG_HOST", "127.0.0.1")
PG_PORT = int(os.environ.get("IMS_TEST_PG_PORT", "54321"))
POOLER_PORT = int(os.environ.get("IMS_TEST_POOLER_PORT", "64321"))
PG_ADMIN_USER = os.environ.get("IMS_TEST_PG_ADMIN_USER", "postgres")
PG_ADMIN_PASSWORD = os.environ.get("IMS_TEST_PG_ADMIN_PASSWORD", "ims_local_dev")
CLUSTER_REF = "test-shared-1"

START_HINT = (
    "The test database stack is not reachable. Start it with:\n"
    "  IMS_PG_PORT=54321 IMS_POOLER_PORT=64321 IMS_CLUSTER_PURPOSE=test "
    "docker compose -p ims-test -f deploy/local/docker-compose.yml up -d --build --wait"
)

SETUP_ACTOR = Actor("system:test-setup")
ALL_MODULES = frozenset(m.value for m in LicenceModule)

#: Services whose signing keys exist in the test secrets store.
SERVICES = ("ims-core", "ims-worker", "tenant-web-bff", "ims-platform")


@dataclass
class Stack:
    cluster: ClusterAdmin
    root: Path
    #: The pipeline identity: reads and writes every reference, migration secrets included.
    pipeline_secrets: FileSecretsStore
    #: What Core's identity may read.
    core_secrets: FileSecretsStore
    #: What the Platform Service's identity may read.
    platform_secrets: FileSecretsStore
    object_store: FileObjectStore
    service_keys: dict[str, KeySet] = field(default_factory=dict)

    @property
    def secrets_root(self) -> Path:
        return self.root / "secrets"

    @property
    def objects_root(self) -> Path:
        return self.root / "objects"

    def pooled_engine(self, database: str, user: str, password: str, *, pool_size: int = 2):
        return create_pooler_engine(
            host=PG_HOST,
            port=POOLER_PORT,
            database=database,
            user=user,
            password=password,
            application_name="ims-tests",
            pool_size=pool_size,
            max_overflow=0,
            pool_timeout_s=10,
            sslmode="disable",
        )

    async def app_engine(self, target: CustomerDatabase, *, pool_size: int = 2):
        """Engine as a customer's application role, through the pooler."""
        credential = await self.pipeline_secrets.get(target.app_secret_ref)
        return self.pooled_engine(
            target.database_name, target.app_role, credential["password"], pool_size=pool_size
        )

    async def migration_engine(self, target: CustomerDatabase):
        """Engine as a customer's migration role, connected directly (never through the pooler)."""
        credential = await self.pipeline_secrets.get(target.migration_secret_ref)
        return self.cluster.engine_as(target.database_name, target.migration_role, credential["password"])


@dataclass(frozen=True)
class Customer:
    id: UUID
    code: str
    db: CustomerDatabase
    licence_id: UUID
    valid_until: datetime


async def wipe_test_cluster(cluster: ClusterAdmin) -> None:
    """Drop every IMS database and role. Refuses to touch a cluster not marked as the test one."""
    engine = cluster.admin_engine()
    try:
        async with engine.connect() as raw:
            conn = await raw.execution_options(isolation_level="AUTOCOMMIT")
            purpose = (
                await conn.execute(text("SELECT current_setting('ims.cluster_purpose', true)"))
            ).scalar_one()
            if purpose != "test":
                raise RuntimeError(
                    f"refusing to wipe {cluster.host}:{cluster.port}: ims.cluster_purpose is {purpose!r}, not 'test'"
                )
            databases = (
                await conn.execute(
                    text(
                        "SELECT datname FROM pg_database "
                        "WHERE datname LIKE 'ims\\_c\\_%' ESCAPE '\\' OR datname = 'ims_control_plane'"
                    )
                )
            ).scalars()
            for name in list(databases):
                await conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
            roles = (
                await conn.execute(
                    text(
                        "SELECT rolname FROM pg_roles WHERE rolname ~ '^ims_(app|mig|breakglass)_' "
                        "OR rolname IN ('platform_app', 'platform_migrator')"
                    )
                )
            ).scalars()
            for name in list(roles):
                await conn.execute(text(f'DROP ROLE "{name}"'))
    except OperationalError as exc:
        raise RuntimeError(START_HINT) from exc
    finally:
        await engine.dispose()


async def bootstrap(root: Path) -> Stack:
    """Empty cluster -> migrated Control-Plane database plus every key the services need."""
    cluster = ClusterAdmin(
        cluster_ref=CLUSTER_REF,
        host=PG_HOST,
        port=PG_PORT,
        user=PG_ADMIN_USER,
        password=PG_ADMIN_PASSWORD,
        sslmode="disable",
        pooler_endpoint=f"{PG_HOST}:{POOLER_PORT}",
    )
    await wipe_test_cluster(cluster)
    secrets_root = root / "secrets"
    stack = Stack(
        cluster=cluster,
        root=root,
        pipeline_secrets=FileSecretsStore(secrets_root, readable=("*",), writable=("*",)),
        core_secrets=FileSecretsStore(secrets_root, readable=CORE_READABLE_SECRETS),
        platform_secrets=FileSecretsStore(secrets_root, readable=PLATFORM_READABLE_SECRETS),
        object_store=FileObjectStore(root / "objects"),
    )
    put = stack.pipeline_secrets.put
    await put(cluster_admin_ref(CLUSTER_REF), cluster.to_secret())
    await put("core/token-signing", KeySet.generate("core-2026-11").to_secret())
    bundle_keys = KeySet.generate("bundle-2026-11")
    await put("platform/bundle-signing", bundle_keys.to_secret())
    await put("platform/bundle-verify", bundle_keys.public_secret())
    await put("platform/login-pepper", new_key_secret())
    await put("shared/directory-lookup-key", new_key_secret())
    await put("core/mfa-encryption", SecretBox.new_ring())
    await put("platform/token-signing", KeySet.generate("platform-2026-11").to_secret())
    await put("platform/sealing-keys", SecretBox.new_ring("platform-seal-1"))
    for service in SERVICES:
        keys = KeySet.generate(f"{service}-1")
        stack.service_keys[service] = keys
        await put(f"services/{service}/signing", keys.to_secret())
        await put(f"services/{service}/verify", keys.public_secret())
    await provision_control_plane(cluster, stack.pipeline_secrets)
    await migrate_control_plane(cluster, stack.pipeline_secrets)
    return stack


async def onboard_customer(
    stack: Stack,
    registry: RegistryService,
    code: str,
    *,
    now: datetime,
    valid_for_days: int = 365,
    grace_days: int = 14,
    modules: frozenset[str] = ALL_MODULES,
    gxp_mode: bool = False,
    activate: bool = True,
) -> Customer:
    """The provisioning sequence of LLD 6.6, using the real pipeline and Registry commands:
    register -> create database and roles -> migrate -> licence -> activate."""
    customer_id = await registry.register_customer(
        code=code,
        legal_name=f"Test customer {code}",
        actor=SETUP_ACTOR,
        gxp_mode=gxp_mode,
        placement=Placement.DEDICATED if gxp_mode else Placement.SHARED,
    )
    target = await provision_customer_database(stack.cluster, stack.pipeline_secrets, code)
    await registry.register_database(
        customer_id=customer_id,
        cluster_ref=stack.cluster.cluster_ref,
        pooler_endpoint=stack.cluster.pooler_endpoint,
        database_name=target.database_name,
        app_role=target.app_role,
        secret_ref=target.app_secret_ref,
        actor=SETUP_ACTOR,
    )
    outcome = await migrate_customer_database(stack.cluster, stack.pipeline_secrets, code)
    await registry.record_database_state(
        customer_id, actor=SETUP_ACTOR, status=DatabaseStatus.READY, schema_version=outcome.to_version
    )
    valid_until = now + timedelta(days=valid_for_days)
    licence_id = await registry.create_licence(
        customer_id=customer_id,
        licence_no=f"LIC-{code}-1",
        valid_from=now - timedelta(days=1),
        valid_until=valid_until,
        grace_days=grace_days,
        max_sites=5,
        max_users=200,
        modules=modules,
        actor=SETUP_ACTOR,
    )
    await registry.activate_licence(licence_id, actor=SETUP_ACTOR)
    if activate:
        await registry.activate_customer(customer_id, actor=SETUP_ACTOR)
    return Customer(id=customer_id, code=code, db=target, licence_id=licence_id, valid_until=valid_until)
