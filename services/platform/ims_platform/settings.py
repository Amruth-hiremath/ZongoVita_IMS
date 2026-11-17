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
