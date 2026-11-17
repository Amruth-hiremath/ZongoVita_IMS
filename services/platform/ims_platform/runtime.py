"""Wiring of the Platform Service's long-lived objects."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from ims_common.clock import Clock, SystemClock
from ims_common.objectstore import FileObjectStore, ObjectStore
from ims_common.pg import create_pooler_engine
from ims_common.secrets import FileSecretsStore, SecretsStore
from ims_common.service_auth import ServiceTokenVerifier
from ims_common.tokens import KeySet
from ims_contracts.platform_api import SERVICE_AUDIENCE_PLATFORM_INTERNAL
from ims_platform.bundle import BundlePublisher
from ims_platform.registry import RegistryService
from ims_platform.settings import PlatformSettings

#: What the Platform Service identity may read from the secrets store. Customer database
#: application and migration credentials are deliberately absent (AD-13).
PLATFORM_READABLE_SECRETS = ("platform/*", "services/*/verify")


@dataclass
class PlatformRuntime:
    settings: PlatformSettings
    engine: AsyncEngine
    registry: RegistryService
    bundle_publisher: BundlePublisher
    service_verifier: ServiceTokenVerifier
    clock: Clock

    async def aclose(self) -> None:
        await self.engine.dispose()


def build_secrets_store(settings: PlatformSettings) -> SecretsStore:
    return FileSecretsStore(settings.secrets_root, readable=PLATFORM_READABLE_SECRETS)


def build_object_store(settings: PlatformSettings) -> ObjectStore:
    return FileObjectStore(settings.object_store_root)


async def build_runtime(
    settings: PlatformSettings,
    *,
    secrets: SecretsStore | None = None,
    object_store: ObjectStore | None = None,
    clock: Clock | None = None,
) -> PlatformRuntime:
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
    return PlatformRuntime(
        settings=settings,
        engine=engine,
        registry=registry,
        bundle_publisher=BundlePublisher(registry, object_store, signing_keys, clock),
        service_verifier=ServiceTokenVerifier(SERVICE_AUDIENCE_PLATFORM_INTERNAL, trusted, clock),
        clock=clock,
    )
