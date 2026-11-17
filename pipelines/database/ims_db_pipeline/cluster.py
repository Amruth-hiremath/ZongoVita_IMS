"""Administrative access to a PostgreSQL cluster, for the pipeline identity only."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from ims_common.pg import create_direct_engine
from ims_common.secrets import SecretsStore, validate_ref


def cluster_admin_ref(cluster_ref: str) -> str:
    return validate_ref(f"clusters/{cluster_ref}/admin")


@dataclass(frozen=True)
class ClusterAdmin:
    """A cluster and the credential that may create databases and roles on it.

    ``pooler_endpoint`` is what applications use and what the Registry records; the pipeline
    itself always connects directly (LLD 6.5).
    """

    cluster_ref: str
    host: str
    port: int
    user: str
    password: str
    sslmode: str
    pooler_endpoint: str

    @classmethod
    async def from_secrets(cls, secrets: SecretsStore, cluster_ref: str) -> ClusterAdmin:
        value = await secrets.get(cluster_admin_ref(cluster_ref))
        return cls(
            cluster_ref=cluster_ref,
            host=value["host"],
            port=int(value["port"]),
            user=value["user"],
            password=value["password"],
            sslmode=value.get("sslmode", "require"),
            pooler_endpoint=value["pooler_endpoint"],
        )

    def to_secret(self) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "sslmode": self.sslmode,
            "pooler_endpoint": self.pooler_endpoint,
        }

    def admin_engine(self, database: str = "postgres") -> AsyncEngine:
        return self.engine_as(database, self.user, self.password)

    def engine_as(self, database: str, user: str, password: str) -> AsyncEngine:
        return create_direct_engine(
            host=self.host,
            port=self.port,
            database=database,
            user=user,
            password=password,
            application_name="ims-db-pipeline",
            sslmode=self.sslmode,
        )
