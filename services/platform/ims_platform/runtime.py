"""Wiring of the Platform Service's long-lived objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from ims_common.clock import Clock, SystemClock
from ims_common.credentials import PasswordHasher, SecretBox
from ims_common.identifiers import key_from_secret
from ims_common.objectstore import FileObjectStore, ObjectStore
from ims_common.pg import create_pooler_engine
from ims_common.secrets import FileSecretsStore, SecretsStore
from ims_common.service_auth import ServiceTokenIssuer, ServiceTokenVerifier
from ims_common.tokens import KeySet, TokenCodec
from ims_contracts.enums import Placement
from ims_contracts.platform_api import SERVICE_AUDIENCE_PLATFORM_INTERNAL
from ims_platform.accounts import PLATFORM_ISSUER, AccountsService
from ims_platform.admin_queries import AdminQueries
from ims_platform.bundle import BundlePublisher
from ims_platform.directory import DirectoryService
from ims_platform.provisioning import (
    CorePort,
    HttpCore,
    PipelinePort,
    ProvisioningService,
    SubprocessPipeline,
)
from ims_platform.registry import RegistryService
from ims_platform.settings import PlatformSettings

#: What the Platform Service identity may read from the secrets store. Customer database
#: application and migration credentials, and every cluster credential, are deliberately absent
#: (AD-13): provisioning DDL runs in the database pipeline's own process and identity.
PLATFORM_READABLE_SECRETS = (
    "platform/*",
    "services/*/verify",
    "services/ims-platform/signing",
    "shared/directory-lookup-key",
)


@dataclass
class PlatformRuntime:
    settings: PlatformSettings
    engine: AsyncEngine
    registry: RegistryService
    directory: DirectoryService
    bundle_publisher: BundlePublisher
    service_verifier: ServiceTokenVerifier
    clock: Clock
    accounts: AccountsService
    queries: AdminQueries
    provisioning: ProvisioningService
    http: httpx.AsyncClient | None = None

    async def aclose(self) -> None:
        await self.provisioning.wait_for_background()
        if self.http is not None:
            await self.http.aclose()
        await self.engine.dispose()


def build_secrets_store(settings: PlatformSettings) -> SecretsStore:
    return FileSecretsStore(settings.secrets_root, readable=PLATFORM_READABLE_SECRETS)


def build_object_store(settings: PlatformSettings) -> ObjectStore:
    return FileObjectStore(settings.object_store_root)


def build_pipeline(settings: PlatformSettings) -> PipelinePort:
    clusters = {
        placement: ref
        for placement, ref in (
            (Placement.SHARED, settings.shared_cluster_ref),
            (Placement.DEDICATED, settings.dedicated_cluster_ref),
        )
        if ref
    }
    env = (
        {"IMS_PIPELINE_SECRETS_ROOT": str(settings.pipeline_secrets_root)}
        if settings.pipeline_secrets_root
        else None
    )
    return SubprocessPipeline(settings.pipeline_command, cluster_refs=clusters, env=env)


async def build_runtime(
    settings: PlatformSettings,
    *,
    secrets: SecretsStore | None = None,
    object_store: ObjectStore | None = None,
    clock: Clock | None = None,
    pipeline: PipelinePort | None = None,
    core: CorePort | None = None,
    core_transport: httpx.AsyncBaseTransport | None = None,
    hasher: PasswordHasher | None = None,
) -> PlatformRuntime:
    """``pipeline``, ``core`` and ``core_transport`` let tests run the database pipeline and IMS
    Core in-process."""
    clock = clock or SystemClock()
    secrets = secrets or build_secrets_store(settings)
    object_store = object_store or build_object_store(settings)

    db_secret = await secrets.get(settings.db_secret_ref)
    engine = create_pooler_engine(
        host=settings.db_pooler_host,
        port=settings.db_pooler_port,
        database=settings.db_name,
        user=settings.db_user,
        password=db_secret["password"],
        application_name=f"ims-platform/{settings.instance}",
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout_s=5,
        sslmode=settings.db_sslmode,
    )
    registry = RegistryService(engine, clock)
    signing_keys = KeySet.from_secret(await secrets.get(settings.bundle_signing_key_ref))
    trusted = {
        name: KeySet.from_secret(await secrets.get(ref)) for name, ref in settings.trusted_callers.items()
    }
    box = SecretBox(await secrets.get(settings.sealing_key_ref))
    accounts = AccountsService(
        engine,
        codec=TokenCodec(
            KeySet.from_secret(await secrets.get(settings.token_signing_key_ref)), PLATFORM_ISSUER, clock
        ),
        box=box,
        hasher=hasher
        or PasswordHasher(
            time_cost=settings.password_time_cost,
            memory_kib=settings.password_memory_kib,
            parallelism=settings.password_parallelism,
        ),
        clock=clock,
    )

    http: httpx.AsyncClient | None = None
    if core is None:
        http = httpx.AsyncClient(
            base_url=settings.core_base_url, timeout=settings.core_timeout_seconds, transport=core_transport
        )
        service_keys = KeySet.from_secret(await secrets.get(settings.service_signing_key_ref))
        core = HttpCore(http, ServiceTokenIssuer(settings.service_name, service_keys, clock))

    return PlatformRuntime(
        settings=settings,
        engine=engine,
        registry=registry,
        directory=DirectoryService(
            engine,
            pepper=key_from_secret(await secrets.get(settings.login_pepper_ref)),
            lookup_key=key_from_secret(await secrets.get(settings.directory_lookup_key_ref)),
            clock=clock,
        ),
        bundle_publisher=BundlePublisher(registry, object_store, signing_keys, clock),
        service_verifier=ServiceTokenVerifier(SERVICE_AUDIENCE_PLATFORM_INTERNAL, trusted, clock),
        clock=clock,
        accounts=accounts,
        queries=AdminQueries(engine, clock),
        provisioning=ProvisioningService(
            engine,
            registry,
            pipeline=pipeline or build_pipeline(settings),
            core=core,
            box=box,
            clock=clock,
            stale_after=timedelta(minutes=settings.provisioning_stale_minutes),
        ),
        http=http,
    )
