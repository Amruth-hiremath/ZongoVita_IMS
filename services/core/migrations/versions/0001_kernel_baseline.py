"""Kernel baseline: schemas, audit trail, outbox, idempotency keys, settings.

Creates the thirteen customer schemas (LD-05) and the tables every command depends on
(AD-08): the append-only audit log, the transactional outbox, idempotency keys and the
settings store. Business tables arrive with their modules in later revisions.

Revision ID: 0001
Revises:
"""

from ims_common.ddl import execute_statements
from ims_core.schema.access import CUSTOMER_SCHEMAS
from ims_core.schema.ddl import app_role, append_only_triggers
from ims_core.schema.partitions import PARTITIONED_TABLES

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    app = app_role()
    statements: list[str] = [
        # Nothing lives in public, and nobody but the owner may use it.
        "REVOKE ALL ON SCHEMA public FROM PUBLIC",
    ]
    for schema in CUSTOMER_SCHEMAS:
        statements += [f"CREATE SCHEMA {schema}", f"GRANT USAGE ON SCHEMA {schema} TO {app}"]

    statements += [
        # ------------------------------------------------------------------ append-only guard
        """
        CREATE FUNCTION audit.reject_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '%.% is append-only: % is not allowed', TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """,
        # -------------------------------------------------------------------------- audit log
        "CREATE SEQUENCE audit.audit_log_seq",
        """
        CREATE TABLE audit.audit_log (
            -- Partition key and ordering columns are set by default at insert and never supplied
            -- by the application (column-level INSERT grant below).
            occurred_at timestamptz NOT NULL DEFAULT now(),
            seq         bigint      NOT NULL DEFAULT nextval('audit.audit_log_seq'),
            txid        xid8        NOT NULL DEFAULT pg_current_xact_id(),
            actor_type  text        NOT NULL,
            actor_id    uuid,
            action      text        NOT NULL,
            entity_type text        NOT NULL,
            entity_id   text        NOT NULL,
            site_id     uuid,
            before      jsonb,
            after       jsonb,
            reason      text,
            request_id  text,
            source      text        NOT NULL,
            CONSTRAINT audit_log_pkey PRIMARY KEY (occurred_at, seq),
            CONSTRAINT audit_log_actor_type_check
                CHECK (actor_type IN ('user', 'api_client', 'support', 'system', 'break_glass')),
            CONSTRAINT audit_log_actor_present CHECK (actor_type = 'system' OR actor_id IS NOT NULL),
            CONSTRAINT audit_log_source_check CHECK (source IN ('ui', 'api', 'worker', 'system')),
            CONSTRAINT audit_log_reason_not_blank CHECK (reason IS NULL OR btrim(reason) <> '')
        ) PARTITION BY RANGE (occurred_at)
        """,
        "CREATE INDEX audit_log_entity ON audit.audit_log (entity_type, entity_id, occurred_at)",
        "CREATE INDEX audit_log_actor ON audit.audit_log (actor_id, occurred_at)",
        "CREATE INDEX audit_log_site ON audit.audit_log (site_id, occurred_at)",
        *append_only_triggers("audit", "audit_log"),
        f"GRANT SELECT ON audit.audit_log TO {app}",
        f"""
        GRANT INSERT (actor_type, actor_id, action, entity_type, entity_id, site_id, before, after,
                      reason, request_id, source)
            ON audit.audit_log TO {app}
        """,
        f"GRANT USAGE ON SEQUENCE audit.audit_log_seq TO {app}",
        # ----------------------------------------------------------------------------- outbox
        "CREATE SEQUENCE integration.outbox_events_seq",
        """
        CREATE TABLE integration.outbox_events (
            occurred_at     timestamptz NOT NULL DEFAULT now(),
            id              uuid        NOT NULL,
            -- seq is allocation order; (txid, seq) with the xmin horizon gives the commit-safe
            -- feed order (LD-52).
            seq             bigint      NOT NULL DEFAULT nextval('integration.outbox_events_seq'),
            txid            xid8        NOT NULL DEFAULT pg_current_xact_id(),
            event_type      text        NOT NULL,
            event_version   integer     NOT NULL DEFAULT 1,
            subject_type    text        NOT NULL,
            subject_id      text        NOT NULL,
            subject_version bigint      NOT NULL,
            payload         jsonb       NOT NULL,
            trace_id        text,
            status          text        NOT NULL DEFAULT 'pending',
            dispatched_at   timestamptz,
            CONSTRAINT outbox_events_pkey PRIMARY KEY (occurred_at, id),
            CONSTRAINT outbox_events_type_format CHECK (event_type ~ '^[a-z_]+(\\.[a-z_]+)+$'),
            CONSTRAINT outbox_events_version_positive CHECK (event_version >= 1),
            CONSTRAINT outbox_events_subject_version_positive CHECK (subject_version >= 1),
            CONSTRAINT outbox_events_status_check CHECK (status IN ('pending', 'dispatched')),
            CONSTRAINT outbox_events_dispatch_consistent
                CHECK ((status = 'dispatched') = (dispatched_at IS NOT NULL))
        ) PARTITION BY RANGE (occurred_at)
        """,
        "CREATE INDEX outbox_events_feed ON integration.outbox_events (txid, seq)",
        "CREATE INDEX outbox_events_pending ON integration.outbox_events (seq) WHERE status = 'pending'",
        """
        CREATE INDEX outbox_events_subject
            ON integration.outbox_events (subject_type, subject_id, subject_version)
        """,
        # Events stay in this one table (LD-67): never deleted row by row, never truncated, and a
        # dispatched event is never reopened.
        """
        CREATE FUNCTION integration.outbox_events_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP <> 'UPDATE' THEN
                RAISE EXCEPTION 'integration.outbox_events: % is not allowed', TG_OP
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.status = 'dispatched' THEN
                RAISE EXCEPTION 'integration.outbox_events: a dispatched event is immutable'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """,
        """
        CREATE TRIGGER outbox_events_guard BEFORE UPDATE OR DELETE ON integration.outbox_events
            FOR EACH ROW EXECUTE FUNCTION integration.outbox_events_guard()
        """,
        """
        CREATE TRIGGER outbox_events_no_truncate BEFORE TRUNCATE ON integration.outbox_events
            FOR EACH STATEMENT EXECUTE FUNCTION audit.reject_change()
        """,
        f"GRANT SELECT ON integration.outbox_events TO {app}",
        f"""
        GRANT INSERT (id, event_type, event_version, subject_type, subject_id, subject_version,
                      payload, trace_id)
            ON integration.outbox_events TO {app}
        """,
        f"GRANT UPDATE (status, dispatched_at) ON integration.outbox_events TO {app}",
        f"GRANT USAGE ON SEQUENCE integration.outbox_events_seq TO {app}",
        # ------------------------------------------------------------------- idempotency keys
        """
        CREATE TABLE integration.idempotency_keys (
            principal_id  uuid        NOT NULL,
            key           text        NOT NULL,
            endpoint      text        NOT NULL,
            request_hash  bytea       NOT NULL,
            status_code   integer,
            response_body text,
            created_at    timestamptz NOT NULL DEFAULT now(),
            expires_at    timestamptz NOT NULL,
            CONSTRAINT idempotency_keys_pkey PRIMARY KEY (principal_id, key),
            CONSTRAINT idempotency_keys_key_length CHECK (char_length(key) BETWEEN 8 AND 128),
            CONSTRAINT idempotency_keys_hash_length CHECK (octet_length(request_hash) = 32),
            CONSTRAINT idempotency_keys_response_complete
                CHECK ((status_code IS NULL) = (response_body IS NULL))
        )
        """,
        "CREATE INDEX idempotency_keys_expiry ON integration.idempotency_keys (expires_at)",
        # On the DELETE exception list, but only once expired.
        """
        CREATE FUNCTION integration.idempotency_keys_delete_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.expires_at > now() THEN
                RAISE EXCEPTION 'integration.idempotency_keys: only expired keys may be deleted'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN OLD;
        END $$
        """,
        """
        CREATE TRIGGER idempotency_keys_delete_guard BEFORE DELETE ON integration.idempotency_keys
            FOR EACH ROW EXECUTE FUNCTION integration.idempotency_keys_delete_guard()
        """,
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON integration.idempotency_keys TO {app}",
        # --------------------------------------------------------------------------- settings
        """
        CREATE TABLE config.settings (
            key        text        PRIMARY KEY,
            value      jsonb       NOT NULL,
            version    integer     NOT NULL DEFAULT 1,
            created_at timestamptz NOT NULL DEFAULT now(),
            created_by uuid,
            updated_at timestamptz NOT NULL DEFAULT now(),
            updated_by uuid,
            CONSTRAINT settings_key_format CHECK (key ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'),
            CONSTRAINT settings_version_positive CHECK (version >= 1)
        )
        """,
        f"GRANT SELECT, INSERT, UPDATE ON config.settings TO {app}",
    ]
    # Parent tables need a default partition from the start; the pipeline creates the monthly
    # partitions right after the upgrade and keeps them three months ahead.
    statements += [table.create_default_sql() for table in PARTITIONED_TABLES]
    execute_statements(statements)


def downgrade() -> None:
    raise NotImplementedError("migrations only expand (LLD 6.7); roll forward instead")
