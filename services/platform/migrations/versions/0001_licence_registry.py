"""Licence Registry, Login Directory, change feed and platform audit (LLD section 4).

The Control-Plane database holds customers, licences, entitlements, database locations and the
login directory. It never holds customer business data (tenancy rule 6).

Revision ID: 0001
Revises:
"""

from ims_common.ddl import execute_statements

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

STATEMENTS = [
    "CREATE SCHEMA platform",
    # ------------------------------------------------------------------------------ customers
    """
    CREATE TABLE platform.customers (
        id          uuid        PRIMARY KEY,
        code        text        NOT NULL,
        legal_name  text        NOT NULL,
        status      text        NOT NULL DEFAULT 'provisioning',
        gxp_mode    boolean     NOT NULL DEFAULT false,
        gxp_locked  boolean     NOT NULL DEFAULT false,
        placement   text        NOT NULL DEFAULT 'shared',
        created_at  timestamptz NOT NULL DEFAULT now(),
        created_by  text        NOT NULL,
        updated_at  timestamptz NOT NULL DEFAULT now(),
        updated_by  text        NOT NULL,
        version     integer     NOT NULL DEFAULT 1,
        CONSTRAINT customers_code_key UNIQUE (code),
        -- The code becomes part of database and role names (ims_app_<code>), hence the format.
        CONSTRAINT customers_code_format CHECK (code ~ '^[a-z][a-z0-9_]{1,29}$'),
        CONSTRAINT customers_legal_name_present CHECK (btrim(legal_name) <> ''),
        CONSTRAINT customers_status_check
            CHECK (status IN ('provisioning', 'active', 'suspended', 'terminated')),
        CONSTRAINT customers_placement_check CHECK (placement IN ('shared', 'dedicated')),
        CONSTRAINT customers_gxp_lock_needs_mode CHECK (NOT gxp_locked OR gxp_mode),
        -- GxP customers get per-customer keys and therefore a dedicated instance (AD-61, AD-81).
        CONSTRAINT customers_gxp_needs_dedicated CHECK (NOT gxp_mode OR placement = 'dedicated')
    )
    """,
    """
    CREATE FUNCTION platform.customers_guard() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.id <> OLD.id OR NEW.code <> OLD.code THEN
            RAISE EXCEPTION 'customer id and code are immutable'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        -- Licence state machine, customer-status part (AD-78):
        -- provisioning -> active; active <-> suspended; active|suspended -> terminated (final).
        IF NEW.status <> OLD.status AND NOT (
               (OLD.status = 'provisioning' AND NEW.status = 'active')
            OR (OLD.status = 'active'       AND NEW.status IN ('suspended', 'terminated'))
            OR (OLD.status = 'suspended'    AND NEW.status IN ('active', 'terminated'))
        ) THEN
            RAISE EXCEPTION 'customer status cannot change from % to %', OLD.status, NEW.status
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        -- Once GxP data exists the lock is permanent, and with it GxP mode (AD-81).
        IF OLD.gxp_locked AND NOT NEW.gxp_locked THEN
            RAISE EXCEPTION 'gxp_locked cannot be cleared'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        RETURN NEW;
    END $$
    """,
    """
    CREATE TRIGGER customers_guard BEFORE UPDATE ON platform.customers
        FOR EACH ROW EXECUTE FUNCTION platform.customers_guard()
    """,
    # ------------------------------------------------------------------------------- licences
    """
    CREATE TABLE platform.licences (
        id            uuid        PRIMARY KEY,
        customer_id   uuid        NOT NULL REFERENCES platform.customers (id),
        licence_no    text        NOT NULL,
        record_status text        NOT NULL DEFAULT 'draft',
        valid_from    timestamptz NOT NULL,
        valid_until   timestamptz NOT NULL,
        grace_days    integer     NOT NULL DEFAULT 14,
        max_sites     integer     NOT NULL,
        max_users     integer     NOT NULL,
        created_at    timestamptz NOT NULL DEFAULT now(),
        created_by    text        NOT NULL,
        updated_at    timestamptz NOT NULL DEFAULT now(),
        updated_by    text        NOT NULL,
        version       integer     NOT NULL DEFAULT 1,
        CONSTRAINT licences_licence_no_key UNIQUE (licence_no),
        CONSTRAINT licences_record_status_check
            CHECK (record_status IN ('draft', 'active', 'superseded')),
        CONSTRAINT licences_validity_order CHECK (valid_until > valid_from),
        CONSTRAINT licences_grace_days_range CHECK (grace_days BETWEEN 0 AND 366),
        CONSTRAINT licences_max_sites_positive CHECK (max_sites >= 1),
        CONSTRAINT licences_max_users_positive CHECK (max_users >= 1)
    )
    """,
    # At most one active licence per customer.
    """
    CREATE UNIQUE INDEX licences_one_active_per_customer
        ON platform.licences (customer_id) WHERE record_status = 'active'
    """,
    "CREATE INDEX licences_customer ON platform.licences (customer_id)",
    """
    CREATE FUNCTION platform.licences_guard() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.id <> OLD.id OR NEW.customer_id <> OLD.customer_id OR NEW.licence_no <> OLD.licence_no THEN
            RAISE EXCEPTION 'licence identity is immutable'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        IF NEW.record_status <> OLD.record_status AND NOT (
               (OLD.record_status = 'draft'  AND NEW.record_status = 'active')
            OR (OLD.record_status = 'active' AND NEW.record_status = 'superseded')
        ) THEN
            RAISE EXCEPTION 'licence record cannot change from % to %', OLD.record_status, NEW.record_status
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        -- Terms are fixed once a licence has been activated; a renewal is a new licence record.
        IF OLD.record_status <> 'draft' AND (
               NEW.valid_from <> OLD.valid_from OR NEW.valid_until <> OLD.valid_until
            OR NEW.grace_days <> OLD.grace_days OR NEW.max_sites <> OLD.max_sites
            OR NEW.max_users <> OLD.max_users
        ) THEN
            RAISE EXCEPTION 'terms of an activated licence are immutable'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        RETURN NEW;
    END $$
    """,
    """
    CREATE TRIGGER licences_guard BEFORE UPDATE ON platform.licences
        FOR EACH ROW EXECUTE FUNCTION platform.licences_guard()
    """,
    # -------------------------------------------------------------------------------- modules
    """
    CREATE TABLE platform.modules (
        code   text    PRIMARY KEY,
        name   text    NOT NULL,
        active boolean NOT NULL DEFAULT true,
        CONSTRAINT modules_code_format CHECK (code ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$')
    )
    """,
    """
    CREATE TABLE platform.licence_modules (
        licence_id  uuid NOT NULL REFERENCES platform.licences (id),
        module_code text NOT NULL REFERENCES platform.modules (code),
        PRIMARY KEY (licence_id, module_code)
    )
    """,
    """
    CREATE FUNCTION platform.licence_modules_guard() RETURNS trigger
    LANGUAGE plpgsql AS $$
    DECLARE
        v_status text;
    BEGIN
        SELECT record_status INTO v_status FROM platform.licences
         WHERE id = COALESCE(NEW.licence_id, OLD.licence_id);
        IF v_status <> 'draft' THEN
            RAISE EXCEPTION 'modules of an activated licence are immutable'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        RETURN COALESCE(NEW, OLD);
    END $$
    """,
    """
    CREATE TRIGGER licence_modules_guard BEFORE INSERT OR UPDATE OR DELETE ON platform.licence_modules
        FOR EACH ROW EXECUTE FUNCTION platform.licence_modules_guard()
    """,
    # Current module tagging (LD-72). The commercial list is owned by Product (open item #5).
    """
    INSERT INTO platform.modules (code, name) VALUES
        ('ims.core',              'IMS core inventory'),
        ('ims.replenishment',     'IMS replenishment planning'),
        ('ims.supplier_register', 'IMS supplier quality register'),
        ('ims.integration',       'IMS public API, webhooks and connectors')
    """,
    # ------------------------------------------------------------------- customer databases
    """
    CREATE TABLE platform.customer_databases (
        id              uuid        PRIMARY KEY,
        customer_id     uuid        NOT NULL REFERENCES platform.customers (id),
        cluster_ref     text        NOT NULL,
        pooler_endpoint text        NOT NULL,
        database_name   text        NOT NULL,
        app_role        text        NOT NULL,
        -- A reference into the secrets store. Never a password (LD-12).
        secret_ref      text        NOT NULL,
        key_ref         text,
        schema_version  text,
        status          text        NOT NULL DEFAULT 'creating',
        created_at      timestamptz NOT NULL DEFAULT now(),
        created_by      text        NOT NULL,
        updated_at      timestamptz NOT NULL DEFAULT now(),
        updated_by      text        NOT NULL,
        version         integer     NOT NULL DEFAULT 1,
        CONSTRAINT customer_databases_customer_key UNIQUE (customer_id),
        CONSTRAINT customer_databases_location_key UNIQUE (cluster_ref, database_name),
        CONSTRAINT customer_databases_endpoint_format CHECK (pooler_endpoint ~ '^[^:\\s]+:[0-9]{1,5}$'),
        CONSTRAINT customer_databases_status_check
            CHECK (status IN ('creating', 'ready', 'migrating', 'failed', 'retired'))
    )
    """,
    # ------------------------------------------------------------------------ login directory
    """
    CREATE TABLE platform.login_directory (
        -- HMAC-SHA256(pepper, normalised identifier): the identifier itself is not stored (LD-10).
        login_hash     bytea       PRIMARY KEY,
        customer_id    uuid        NOT NULL REFERENCES platform.customers (id),
        principal_type text        NOT NULL,
        principal_id   uuid        NOT NULL,
        status         text        NOT NULL,
        reserved_until timestamptz,
        created_at     timestamptz NOT NULL DEFAULT now(),
        updated_at     timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT login_directory_hash_length CHECK (octet_length(login_hash) = 32),
        CONSTRAINT login_directory_principal_type_check CHECK (principal_type IN ('user', 'api_client')),
        CONSTRAINT login_directory_status_check CHECK (status IN ('reserved', 'active', 'disabled')),
        CONSTRAINT login_directory_reservation_expiry
            CHECK ((status = 'reserved') = (reserved_until IS NOT NULL))
    )
    """,
    """
    CREATE INDEX login_directory_principal
        ON platform.login_directory (customer_id, principal_type, principal_id)
    """,
    # ---------------------------------------------------------------------------- change feed
    "CREATE SEQUENCE platform.change_feed_seq",
    """
    CREATE TABLE platform.change_feed (
        seq         bigint      PRIMARY KEY,
        customer_id uuid        NOT NULL REFERENCES platform.customers (id),
        change_type text        NOT NULL,
        changed_at  timestamptz NOT NULL,
        CONSTRAINT change_feed_type_check
            CHECK (change_type IN ('licence', 'status', 'database', 'directory', 'gxp', 'placement'))
    )
    """,
    # Sequence numbers are normally allocated before commit, so a poller reading "seq > N" can
    # skip a row whose transaction commits late. Feed writers are therefore serialised until they
    # commit: the number is taken only while holding a transaction-scoped advisory lock, which
    # makes sequence order equal commit order. Registry changes are rare, so the lock is uncontended.
    """
    CREATE FUNCTION platform.change_feed_assign() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
        PERFORM pg_advisory_xact_lock(4801, 1);
        NEW.seq := nextval('platform.change_feed_seq');
        NEW.changed_at := clock_timestamp();
        RETURN NEW;
    END $$
    """,
    """
    CREATE TRIGGER change_feed_assign BEFORE INSERT ON platform.change_feed
        FOR EACH ROW EXECUTE FUNCTION platform.change_feed_assign()
    """,
    # ------------------------------------------------------------------------- platform audit
    """
    CREATE TABLE platform.platform_audit (
        seq         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        occurred_at timestamptz NOT NULL DEFAULT now(),
        actor       text        NOT NULL,
        action      text        NOT NULL,
        entity_type text        NOT NULL,
        entity_id   text        NOT NULL,
        customer_id uuid        REFERENCES platform.customers (id),
        before      jsonb,
        after       jsonb,
        reason      text,
        request_id  text
    )
    """,
    "CREATE INDEX platform_audit_entity ON platform.platform_audit (entity_type, entity_id, occurred_at)",
    "CREATE INDEX platform_audit_customer ON platform.platform_audit (customer_id, occurred_at)",
    """
    CREATE FUNCTION platform.reject_change() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION '% is append-only: % is not allowed', TG_TABLE_NAME, TG_OP
            USING ERRCODE = 'insufficient_privilege';
    END $$
    """,
    """
    CREATE TRIGGER platform_audit_append_only BEFORE UPDATE OR DELETE ON platform.platform_audit
        FOR EACH ROW EXECUTE FUNCTION platform.reject_change()
    """,
    """
    CREATE TRIGGER platform_audit_no_truncate BEFORE TRUNCATE ON platform.platform_audit
        FOR EACH STATEMENT EXECUTE FUNCTION platform.reject_change()
    """,
    """
    CREATE TRIGGER change_feed_append_only BEFORE UPDATE OR DELETE ON platform.change_feed
        FOR EACH ROW EXECUTE FUNCTION platform.reject_change()
    """,
    # --------------------------------------------------------------------------------- grants
    # platform_app: DML only. Append-only tables are INSERT/SELECT; the single DELETE right is on
    # licence_modules, where the guard trigger limits it to draft licences.
    "GRANT USAGE ON SCHEMA platform TO platform_app",
    """
    GRANT SELECT, INSERT, UPDATE ON
        platform.customers, platform.licences, platform.customer_databases, platform.login_directory
        TO platform_app
    """,
    "GRANT SELECT ON platform.modules TO platform_app",
    "GRANT SELECT, INSERT, DELETE ON platform.licence_modules TO platform_app",
    "GRANT SELECT, INSERT ON platform.change_feed, platform.platform_audit TO platform_app",
    "GRANT USAGE ON SEQUENCE platform.change_feed_seq TO platform_app",
]


def upgrade() -> None:
    execute_statements(STATEMENTS)


def downgrade() -> None:
    raise NotImplementedError("migrations only expand (LLD 6.7); roll forward instead")
