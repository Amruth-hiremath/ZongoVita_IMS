"""Command-line entry point for pipeline jobs.

    ims-db-pipeline provision-control-plane --cluster <ref>
    ims-db-pipeline migrate-control-plane   --cluster <ref>
    ims-db-pipeline provision-customer-db   --cluster <ref> --customer <code>
    ims-db-pipeline migrate-customer-db     --cluster <ref> --customer <code>
    ims-db-pipeline partitions              --cluster <ref> --customer <code> [--drop-expired]

The cluster's administrative credential and endpoints are read from the secrets store at
``clusters/<ref>/admin``. Output is one JSON document per run, for the Platform Service to record.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from ims_common.pg import use_selector_event_loop_on_windows
from ims_common.secrets import FileSecretsStore, SecretsStore
from ims_db_pipeline.cluster import ClusterAdmin
from ims_db_pipeline.migrate import migrate_control_plane, migrate_customer_database
from ims_db_pipeline.partitions import PartitionReport, drop_expired_partitions, ensure_partitions
from ims_db_pipeline.provision import CustomerDatabase, provision_control_plane, provision_customer_database


def _secrets_store() -> SecretsStore:
    # The pipeline identity is the only one entitled to every reference, migration secrets included.
    root = Path(os.environ.get("IMS_PIPELINE_SECRETS_ROOT", ".local/secrets"))
    return FileSecretsStore(root, readable=("*",), writable=("*",))


async def _partitions(
    cluster: ClusterAdmin, secrets: SecretsStore, customer: str, drop_expired: bool
) -> dict:
    target = CustomerDatabase.for_customer(customer)
    credential = await secrets.get(target.migration_secret_ref)
    engine = cluster.engine_as(target.database_name, target.migration_role, credential["password"])
    now = datetime.now(UTC)

    def work(connection) -> PartitionReport:
        report = ensure_partitions(connection, now.date())
        if drop_expired:
            expired = drop_expired_partitions(connection, now)
            report.dropped, report.retained = expired.dropped, expired.retained
        return report

    try:
        async with engine.begin() as conn:
            report = await conn.run_sync(work)
    finally:
        await engine.dispose()
    return asdict(report)


async def _dispatch(args: argparse.Namespace) -> dict:
    secrets = _secrets_store()
    cluster = await ClusterAdmin.from_secrets(secrets, args.cluster)
    if args.command == "provision-control-plane":
        await provision_control_plane(cluster, secrets)
        return {"provisioned": "control-plane"}
    if args.command == "migrate-control-plane":
        outcome = await migrate_control_plane(cluster, secrets)
        return {"database": outcome.database, "from": outcome.from_version, "to": outcome.to_version}
    if args.command == "provision-customer-db":
        target = await provision_customer_database(cluster, secrets, args.customer)
        return {
            "database_name": target.database_name,
            "app_role": target.app_role,
            "secret_ref": target.app_secret_ref,
            "cluster_ref": cluster.cluster_ref,
            "pooler_endpoint": cluster.pooler_endpoint,
        }
    if args.command == "migrate-customer-db":
        outcome = await migrate_customer_database(cluster, secrets, args.customer)
        return {
            "database": outcome.database,
            "from": outcome.from_version,
            "to": outcome.to_version,
            "partitions_created": outcome.partitions.created if outcome.partitions else [],
        }
    if args.command == "partitions":
        return await _partitions(cluster, secrets, args.customer, args.drop_expired)
    raise AssertionError(args.command)  # pragma: no cover


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ims-db-pipeline", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("provision-control-plane", "migrate-control-plane"):
        sub.add_parser(name).add_argument("--cluster", required=True)
    for name in ("provision-customer-db", "migrate-customer-db", "partitions"):
        command = sub.add_parser(name)
        command.add_argument("--cluster", required=True)
        command.add_argument("--customer", required=True)
        if name == "partitions":
            command.add_argument("--drop-expired", action="store_true")
    args = parser.parse_args(argv)
    use_selector_event_loop_on_windows()
    result = asyncio.run(_dispatch(args))
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
