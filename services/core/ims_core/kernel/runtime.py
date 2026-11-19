"""Wiring of Core's long-lived kernel objects."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import httpx

from ims_common.clock import Clock, SystemClock
from ims_common.identifiers import key_from_secret
from ims_common.objectstore import FileObjectStore, ObjectStore
from ims_common.problem import DomainError
from ims_common.secrets import FileSecretsStore, SecretNotFoundError, SecretsStore
from ims_common.service_auth import ServiceTokenIssuer, ServiceTokenVerifier
from ims_common.tokens import KeySet, TokenCodec, TokenError
from ims_contracts.enums import LicenceModule
from ims_contracts.errors import ErrorCode
from ims_contracts.licence import derive_state
from ims_core.kernel.authn import Authenticator, CredentialTokens
from ims_core.kernel.context import Principal, Source, TenantContext
from ims_core.kernel.db import DatabaseRouter
from ims_core.kernel.directory import DirectoryCache, DirectoryClient, HttpDirectoryClient
from ims_core.kernel.licence import (
    BundleSource,
    CustomerUnknownError,
    HttpRegistryClient,
    LicenceGate,
    RegistryClient,
    RegistryUnavailableError,
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
    "shared/directory-lookup-key",
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
    credential_tokens: CredentialTokens
    snapshots: SnapshotStore
    gate: LicenceGate
    router: DatabaseRouter
    tenant_settings: TenantSettings
    bff_verifier: ServiceTokenVerifier | None
    directory: DirectoryCache | None
    http: httpx.AsyncClient | None = None
    registry_client: RegistryClient | None = None
    platform_verifier: ServiceTokenVerifier | None = None

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

    async def credential_context(
        self,
        customer_id: UUID,
        *,
        module: LicenceModule,
        request_id: str,
        source: Source,
        principal: Principal | None = None,
    ) -> TenantContext:
        """Tenant context for a credential endpoint (sign-in, MFA, token refresh, client grant).

        The customer comes from the Login Directory or from a verified credential token, never
        from request input (AD-21). The licence gate applies as on every request; credential
        routes are allowed in read-only state (LD-77).
        """
        snapshot, state = await self.gate.check(customer_id, module=module.value, read_only_ok=True)
        return TenantContext(
            customer_id=snapshot.customer_id,
            customer_code=snapshot.customer_code,
            snapshot=snapshot,
            licence_state=state,
            request_id=request_id,
            source=source,
            principal=principal,
        )

    async def provisioning_context(self, service_token: str, *, request_id: str) -> TenantContext:
        """Tenant context for provisioning step 6 (LLD 6.6): the Platform Service, proven by its
        signed service token, names the customer in the token's claims (AD-21) and the database
        comes from a snapshot the Registry serves only while that customer's run is creating its
        super admin. The context acts as the system; there is no principal."""
        if self.platform_verifier is None or self.registry_client is None:
            raise DomainError(ErrorCode.AUTH_REQUIRED, "provisioning is not enabled on this instance")
        try:
            caller = self.platform_verifier.verify(
                service_token, allowed=frozenset({self.settings.platform_service_name})
            )
            customer_id = UUID(str(caller.claims["cid"]))
        except (TokenError, KeyError, ValueError):
            raise DomainError(ErrorCode.AUTH_REQUIRED, "a platform service token is required") from None
        try:
            snapshot = await self.registry_client.fetch_provisioning_snapshot(customer_id)
        except CustomerUnknownError:
            raise DomainError(
                ErrorCode.NOT_FOUND, "no provisioning run is creating this customer's super admin"
            ) from None
        except RegistryUnavailableError:
            raise DomainError(ErrorCode.PLATFORM_UNAVAILABLE, headers={"Retry-After": "2"}) from None
        return TenantContext(
            customer_id=snapshot.customer_id,
            customer_code=snapshot.customer_code,
            snapshot=snapshot,
            licence_state=derive_state(snapshot, self.clock.now()),
            request_id=request_id,
            source="system",
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
    directory_client: DirectoryClient | None = None,
) -> CoreRuntime:
    """Build the kernel. ``registry_client`` or ``registry_transport`` let tests put the Platform
    Service in-process or simulate its outage."""
    clock = clock or SystemClock()
    secrets = secrets or build_secrets_store(settings)
    object_store = object_store or build_object_store(settings)

    token_keys = KeySet.from_secret(await secrets.get(settings.token_signing_key_ref))
    token_codec = TokenCodec(token_keys, settings.token_issuer, clock)
    authenticator = Authenticator(token_codec)

    http: httpx.AsyncClient | None = None
    if registry_client is None:
        service_keys = KeySet.from_secret(await secrets.get(settings.service_signing_key_ref))
        http = httpx.AsyncClient(
            base_url=settings.platform_base_url,
            timeout=settings.platform_timeout_seconds,
            transport=registry_transport,
        )
        service_tokens = ServiceTokenIssuer(settings.service_name, service_keys, clock)
        registry_client = HttpRegistryClient(http, service_tokens, retries=settings.platform_retries)
        if directory_client is None:
            directory_client = HttpDirectoryClient(http, service_tokens, retries=settings.platform_retries)

    bundle_keys = KeySet.from_secret(await secrets.get(settings.bundle_verify_key_ref))
    snapshots = SnapshotStore(
        registry_client,
        clock,
        ttl_seconds=settings.licence_cache_ttl_seconds,
        probe_backoff_seconds=settings.registry_probe_backoff_seconds,
        bundle=BundleSource(object_store, bundle_keys),
        bundle_cache_seconds=settings.bundle_cache_seconds,
    )

    directory: DirectoryCache | None = None
    if directory_client is not None:
        directory = DirectoryCache(
            directory_client,
            lookup_key=key_from_secret(await secrets.get(settings.directory_lookup_key_ref)),
            clock=clock,
            ttl_seconds=settings.directory_cache_seconds,
            probe_backoff_seconds=settings.registry_probe_backoff_seconds,
            bundle=BundleSource(object_store, bundle_keys),
            bundle_cache_seconds=settings.bundle_cache_seconds,
        )
        snapshots.add_change_listener(directory.on_change)

    try:
        platform_keys = KeySet.from_secret(await secrets.get(settings.platform_verify_key_ref))
        platform_verifier: ServiceTokenVerifier | None = ServiceTokenVerifier(
            SERVICE_AUDIENCE_CORE_INTERNAL, {settings.platform_service_name: platform_keys}, clock
        )
    except SecretNotFoundError:
        platform_verifier = None  # this instance cannot take part in provisioning

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
        credential_tokens=CredentialTokens(token_codec),
        snapshots=snapshots,
        gate=LicenceGate(snapshots, clock),
        router=DatabaseRouter(secrets, settings, clock),
        tenant_settings=TenantSettings(SETTINGS_REGISTRY, clock),
        bff_verifier=bff_verifier,
        directory=directory,
        http=http,
        registry_client=registry_client,
        platform_verifier=platform_verifier,
    )
