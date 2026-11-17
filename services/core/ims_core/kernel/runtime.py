"""Wiring of Core's long-lived kernel objects."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from ims_common.clock import Clock, SystemClock
from ims_common.objectstore import FileObjectStore, ObjectStore
from ims_common.secrets import FileSecretsStore, SecretNotFoundError, SecretsStore
from ims_common.service_auth import ServiceTokenIssuer, ServiceTokenVerifier
from ims_common.tokens import KeySet, TokenCodec
from ims_core.kernel.authn import Authenticator
from ims_core.kernel.db import DatabaseRouter
from ims_core.kernel.licence import (
    BundleSource,
    HttpRegistryClient,
    LicenceGate,
    RegistryClient,
    SnapshotStore,
)
from ims_core.kernel.pipeline import RequestPipeline
from ims_core.kernel.settings import CoreSettings
from ims_core.kernel.stages import PipelineStages
from ims_core.kernel.tenant_settings import SettingsRegistry, TenantSettings

#: What Core's identity may read from the secrets store. Migration and break-glass credentials
#: and every platform signing key are deliberately absent (AD-13, AD-62).
CORE_READABLE_SECRETS = (
    "core/*",
    "customers/*/db-app",
    "services/ims-core/signing",
    "services/*/verify",
    "platform/bundle-verify",
)
SERVICE_AUDIENCE_CORE_INTERNAL = "ims-core-internal"

#: Process-wide registry that modules add their setting definitions to at import time.
SETTINGS_REGISTRY = SettingsRegistry()


@dataclass
class CoreRuntime:
    settings: CoreSettings
    clock: Clock
    secrets: SecretsStore
    authenticator: Authenticator
    snapshots: SnapshotStore
    gate: LicenceGate
    router: DatabaseRouter
    tenant_settings: TenantSettings
    bff_verifier: ServiceTokenVerifier | None
    http: httpx.AsyncClient | None = None

    def pipeline(self, stages: PipelineStages) -> RequestPipeline:
        return RequestPipeline(
            settings=self.settings,
            clock=self.clock,
            authenticator=self.authenticator,
            gate=self.gate,
            router=self.router,
            stages=stages,
            bff_verifier=self.bff_verifier,
        )

    async def aclose(self) -> None:
        await self.router.aclose()
        if self.http is not None:
            await self.http.aclose()


def build_secrets_store(settings: CoreSettings) -> SecretsStore:
    return FileSecretsStore(settings.secrets_root, readable=CORE_READABLE_SECRETS)


def build_object_store(settings: CoreSettings) -> ObjectStore:
    return FileObjectStore(settings.object_store_root)


async def build_runtime(
    settings: CoreSettings,
    *,
    secrets: SecretsStore | None = None,
    object_store: ObjectStore | None = None,
    clock: Clock | None = None,
    registry_client: RegistryClient | None = None,
    registry_transport: httpx.AsyncBaseTransport | None = None,
) -> CoreRuntime:
    """Build the kernel. ``registry_client`` or ``registry_transport`` let tests put the Platform
    Service in-process or simulate its outage."""
    clock = clock or SystemClock()
    secrets = secrets or build_secrets_store(settings)
    object_store = object_store or build_object_store(settings)

    token_keys = KeySet.from_secret(await secrets.get(settings.token_signing_key_ref))
    authenticator = Authenticator(TokenCodec(token_keys, settings.token_issuer, clock))

    http: httpx.AsyncClient | None = None
    if registry_client is None:
        service_keys = KeySet.from_secret(await secrets.get(settings.service_signing_key_ref))
        http = httpx.AsyncClient(
            base_url=settings.platform_base_url,
            timeout=settings.platform_timeout_seconds,
            transport=registry_transport,
        )
        registry_client = HttpRegistryClient(
            http,
            ServiceTokenIssuer(settings.service_name, service_keys, clock),
            retries=settings.platform_retries,
        )

    bundle_keys = KeySet.from_secret(await secrets.get(settings.bundle_verify_key_ref))
    snapshots = SnapshotStore(
        registry_client,
        clock,
        ttl_seconds=settings.licence_cache_ttl_seconds,
        probe_backoff_seconds=settings.registry_probe_backoff_seconds,
        bundle=BundleSource(object_store, bundle_keys),
        bundle_cache_seconds=settings.bundle_cache_seconds,
    )

    try:
        bff_keys = KeySet.from_secret(await secrets.get(settings.bff_verify_key_ref))
        bff_verifier: ServiceTokenVerifier | None = ServiceTokenVerifier(
            SERVICE_AUDIENCE_CORE_INTERNAL, {settings.bff_service_name: bff_keys}, clock
        )
    except SecretNotFoundError:
        # Without the BFF's key no inbound request ID is trusted; Core assigns its own.
        bff_verifier = None

    return CoreRuntime(
        settings=settings,
        clock=clock,
        secrets=secrets,
        authenticator=authenticator,
        snapshots=snapshots,
        gate=LicenceGate(snapshots, clock),
        router=DatabaseRouter(secrets, settings, clock),
        tenant_settings=TenantSettings(SETTINGS_REGISTRY, clock),
        bff_verifier=bff_verifier,
        http=http,
    )
