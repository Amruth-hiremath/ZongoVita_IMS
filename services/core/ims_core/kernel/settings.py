"""Core process configuration (API server and worker). Environment prefix IMS_CORE_.

These are deployment settings. Customer-configurable behaviour lives in each customer's
database (``kernel.tenant_settings``).
"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "dev", "staging", "sandbox", "production"]
LOCAL_ADAPTER_ENVIRONMENTS = frozenset({"local", "test"})


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IMS_CORE_", extra="ignore")

    environment: Environment = "local"
    instance: str = Field(default_factory=socket.gethostname)
    log_level: str = "INFO"

    # Identity of this service and the keys it uses (references into the secrets store).
    service_name: str = "ims-core"
    token_issuer: str = "ims-core"  # noqa: S105 - an issuer name
    token_signing_key_ref: str = "core/token-signing"  # noqa: S105 - a reference
    service_signing_key_ref: str = "services/ims-core/signing"
    bff_service_name: str = "tenant-web-bff"
    bff_verify_key_ref: str = "services/tenant-web-bff/verify"

    # Platform Service (Licence Registry). LLD section 16: 2 s timeout, two retries.
    platform_base_url: str = "http://127.0.0.1:8081"
    platform_timeout_seconds: float = 2.0
    platform_retries: int = 2
    bundle_verify_key_ref: str = "platform/bundle-verify"

    # Licence cache (LLD 6.4, section 16). There is no maximum staleness: last known-good.
    licence_cache_ttl_seconds: float = 60.0
    change_feed_poll_seconds: float = 10.0
    registry_probe_backoff_seconds: float = 5.0
    bundle_cache_seconds: float = 60.0

    # Customer databases through the cluster pooler (LLD 6.5).
    db_sslmode: str = "require"
    db_pool_size: int = 4
    db_max_overflow: int = 4
    db_pool_timeout_seconds: float = 5.0
    db_credential_cache_seconds: float = 600.0
    db_busy_retry_after_seconds: int = 2

    # Unit-of-work retry on deadlock or serialisation failure (LLD 9.1).
    uow_max_retries: int = 3

    secrets_backend: Literal["file"] = "file"
    secrets_root: Path = Path(".local/secrets")
    object_store_backend: Literal["file"] = "file"
    object_store_root: Path = Path(".local/objects")

    @model_validator(mode="after")
    def _local_adapters_stay_local(self) -> CoreSettings:
        if self.environment not in LOCAL_ADAPTER_ENVIRONMENTS and (
            self.secrets_backend == "file" or self.object_store_backend == "file"
        ):
            raise ValueError(
                "file-backed secrets and object stores are for local development and tests only; "
                f"environment {self.environment!r} needs the ZongoVita cloud adapters"
            )
        return self
