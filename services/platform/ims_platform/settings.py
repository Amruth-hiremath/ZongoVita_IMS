"""Platform Service configuration. Values come from the environment (IMS_PLATFORM_*)."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "dev", "staging", "sandbox", "production"]
#: Environments where the file-backed secrets and object stores may be used.
LOCAL_ADAPTER_ENVIRONMENTS = frozenset({"local", "test"})


class PlatformSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IMS_PLATFORM_", extra="ignore")

    environment: Environment = "local"
    instance: str = Field(default_factory=socket.gethostname)
    log_level: str = "INFO"
    bind_host: str = "0.0.0.0"  # noqa: S104 - container default; not routed from the internet
    bind_port: int = 8081

    # Control-Plane database, reached through its cluster's pooler.
    db_pooler_host: str = "127.0.0.1"
    db_pooler_port: int = 64320
    db_name: str = "ims_control_plane"
    db_user: str = "platform_app"
    db_secret_ref: str = "platform/db-app"  # noqa: S105 - a reference, not a secret
    db_sslmode: str = "require"
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # Ports. Only the file adapters exist until ZongoVita cloud's services are known (#31).
    secrets_backend: Literal["file"] = "file"
    secrets_root: Path = Path(".local/secrets")
    object_store_backend: Literal["file"] = "file"
    object_store_root: Path = Path(".local/objects")

    bundle_signing_key_ref: str = "platform/bundle-signing"

    # Staff sign-in for the Platform Console (LLD 6.2 "Platform" tokens, AD-23).
    token_signing_key_ref: str = "platform/token-signing"  # noqa: S105 - a reference
    #: AES-GCM key ring sealing staff TOTP secrets and provisioning hand-over codes.
    sealing_key_ref: str = "platform/sealing-keys"
    password_time_cost: int = 3
    password_memory_kib: int = 65536
    password_parallelism: int = 4

    # This service's own identity towards IMS Core (provisioning step 6, AD-64).
    service_name: str = "ims-platform"
    service_signing_key_ref: str = "services/ims-platform/signing"
    core_base_url: str = "http://127.0.0.1:8080"
    core_timeout_seconds: float = 30.0

    # Provisioning runs (LLD 6.6). The database pipeline runs as its own process and identity;
    # in ZongoVita cloud this is the CI/CD job trigger (U-04).
    pipeline_command: list[str] = Field(default_factory=lambda: ["ims-db-pipeline"])
    #: Where the pipeline process reads its secrets (IMS_PIPELINE_SECRETS_ROOT for that process).
    pipeline_secrets_root: Path | None = None
    shared_cluster_ref: str | None = None
    dedicated_cluster_ref: str | None = None
    provisioning_in_background: bool = True
    provisioning_stale_minutes: int = 15
    # Login Directory keys (LD-10): the pepper never leaves the Platform Service; the lookup key is
    # shared with products so they can resolve identifiers from the snapshot bundle (AD-79).
    login_pepper_ref: str = "platform/login-pepper"
    directory_lookup_key_ref: str = "shared/directory-lookup-key"
    bundle_interval_seconds: float = 300.0  # LD-78: every 5 minutes

    #: Services allowed to call /internal/v1, with the reference of their verification keys.
    trusted_callers: dict[str, str] = Field(
        default_factory=lambda: {
            "ims-core": "services/ims-core/verify",
            "ims-worker": "services/ims-worker/verify",
        }
    )

    @model_validator(mode="after")
    def _local_adapters_stay_local(self) -> PlatformSettings:
        if self.environment not in LOCAL_ADAPTER_ENVIRONMENTS and (
            self.secrets_backend == "file" or self.object_store_backend == "file"
        ):
            raise ValueError(
                "file-backed secrets and object stores are for local development and tests only; "
                f"environment {self.environment!r} needs the ZongoVita cloud adapters"
            )
        return self
