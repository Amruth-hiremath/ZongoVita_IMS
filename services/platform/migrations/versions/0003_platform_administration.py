"""Platform administration: staff accounts, their sessions and recovery codes, provisioning runs
(LLD section 4 platform_users and provisioning_runs, 6.6; AD-23, AD-28).

- platform_users: ZongoVita staff (Argon2id, MFA mandatory, AD-23). The role is one of the two
  staff actors of HLD section 3: system_admin (customers, licences, provisioning, migrations) and
  support_engineer (customer-approved support access, unit 12). Staff are deactivated, never
  deleted. The TOTP secret is kept encrypted on the row (one factor per person, LD-79).
- platform_recovery_codes, platform_sessions: as for customer users (LLD 6.2): ten single-use
  codes stored hashed; refresh rotation with server-side revocation.
- provisioning_runs: one per customer; current_step, status, attempts and last_error (LLD 4),
  plus the non-secret request, per-step results and the super admin's activation code sealed
  until a system admin reveals it once.

Revision ID: 0003
Revises: 0002
"""

from ims_common.ddl import execute_statements

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

STEPS = "'register', 'database', 'register_database', 'migrate', 'initial_users', 'activate', 'done'"

STATEMENTS = [
    # ------------------------------------------------------------------------- staff
    """
    CREATE TABLE platform.platform_users (
        id                       uuid        PRIMARY KEY,
        login_identifier         text        NOT NULL,
        display_name             text        NOT NULL,
        email                    text,
        role                     text        NOT NULL,
        status                   text        NOT NULL DEFAULT 'invited',
        password_hash            text,
        failed_attempts          integer     NOT NULL DEFAULT 0,
        locked_until             timestamptz,
        activation_code_hash     bytea,
        activation_expires_at    timestamptz,
        mfa_ciphertext           bytea,
        mfa_key_id               text,
        mfa_enrolled_at          timestamptz,
        mfa_last_used_step       bigint,
        mfa_pending_ciphertext   bytea,
        mfa_pending_key_id       text,
        mfa_challenge_jti        text,
        mfa_challenge_expires_at timestamptz,
        created_at               timestamptz NOT NULL DEFAULT now(),
        created_by               text        NOT NULL,
        updated_at               timestamptz NOT NULL DEFAULT now(),
        updated_by               text        NOT NULL,
        version                  integer     NOT NULL DEFAULT 1,
        CONSTRAINT platform_users_login_key UNIQUE (login_identifier),
        CONSTRAINT platform_users_login_trimmed
            CHECK (login_identifier = btrim(login_identifier) AND login_identifier <> ''),
        CONSTRAINT platform_users_name_present CHECK (btrim(display_name) <> ''),
        CONSTRAINT platform_users_role_check CHECK (role IN ('system_admin', 'support_engineer')),
        CONSTRAINT platform_users_status_check
            CHECK (status IN ('invited', 'active', 'suspended', 'deactivated')),
        CONSTRAINT platform_users_active_has_password CHECK (status <> 'active' OR password_hash IS NOT NULL),
        CONSTRAINT platform_users_failed_attempts_range CHECK (failed_attempts >= 0),
        CONSTRAINT platform_users_activation_pair
            CHECK ((activation_code_hash IS NULL) = (activation_expires_at IS NULL)),
        CONSTRAINT platform_users_mfa_pair
            CHECK ((mfa_ciphertext IS NULL) = (mfa_key_id IS NULL)
               AND (mfa_ciphertext IS NULL) = (mfa_enrolled_at IS NULL)),
        CONSTRAINT platform_users_mfa_pending_pair
            CHECK ((mfa_pending_ciphertext IS NULL) = (mfa_pending_key_id IS NULL)),
        CONSTRAINT platform_users_challenge_pair
            CHECK ((mfa_challenge_jti IS NULL) = (mfa_challenge_expires_at IS NULL)),
        CONSTRAINT platform_users_version_positive CHECK (version >= 1)
    )
    """,
    """
    CREATE TABLE platform.platform_recovery_codes (
        id         uuid        PRIMARY KEY,
        user_id    uuid        NOT NULL REFERENCES platform.platform_users (id),
        code_hash  bytea       NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        used_at    timestamptz,
        revoked_at timestamptz,
        CONSTRAINT platform_recovery_codes_hash_length CHECK (octet_length(code_hash) = 32),
        CONSTRAINT platform_recovery_codes_user_code_key UNIQUE (user_id, code_hash)
    )
    """,
    """
    CREATE TABLE platform.platform_sessions (
        id                  uuid        PRIMARY KEY,
        user_id             uuid        NOT NULL REFERENCES platform.platform_users (id),
        current_refresh_jti text        NOT NULL,
        mfa_verified_at     timestamptz NOT NULL,
        created_at          timestamptz NOT NULL DEFAULT now(),
        last_refreshed_at   timestamptz NOT NULL,
        idle_expires_at     timestamptz NOT NULL,
        absolute_expires_at timestamptz NOT NULL,
        revoked_at          timestamptz,
        revoke_reason       text,
        CONSTRAINT platform_sessions_idle_within_absolute CHECK (idle_expires_at <= absolute_expires_at),
        CONSTRAINT platform_sessions_revoke_pair CHECK ((revoked_at IS NULL) = (revoke_reason IS NULL))
    )
    """,
    "CREATE INDEX platform_sessions_user ON platform.platform_sessions (user_id) WHERE revoked_at IS NULL",
    # ------------------------------------------------------------------- provisioning runs
    f"""
    CREATE TABLE platform.provisioning_runs (
        id                  uuid        PRIMARY KEY,
        customer_id         uuid        NOT NULL REFERENCES platform.customers (id),
        current_step        text        NOT NULL DEFAULT 'register',
        status              text        NOT NULL DEFAULT 'running',
        attempts            integer     NOT NULL DEFAULT 0,
        last_error          text,
        request             jsonb       NOT NULL,
        results             jsonb       NOT NULL DEFAULT '{{}}',
        super_admin_user_id uuid,
        handover_ciphertext bytea,
        handover_key_id     text,
        requested_by        text        NOT NULL,
        created_at          timestamptz NOT NULL DEFAULT now(),
        updated_at          timestamptz NOT NULL DEFAULT now(),
        completed_at        timestamptz,
        version             integer     NOT NULL DEFAULT 1,
        CONSTRAINT provisioning_runs_one_per_customer UNIQUE (customer_id),
        CONSTRAINT provisioning_runs_step_check CHECK (current_step IN ({STEPS})),
        CONSTRAINT provisioning_runs_status_check CHECK (status IN ('running', 'failed', 'completed')),
        CONSTRAINT provisioning_runs_completed
            CHECK ((status = 'completed') = (current_step = 'done' AND completed_at IS NOT NULL)),
        CONSTRAINT provisioning_runs_failed_has_error CHECK (status <> 'failed' OR last_error IS NOT NULL),
        CONSTRAINT provisioning_runs_handover_pair
            CHECK ((handover_ciphertext IS NULL) = (handover_key_id IS NULL)),
        CONSTRAINT provisioning_runs_attempts_range CHECK (attempts >= 0),
        CONSTRAINT provisioning_runs_version_positive CHECK (version >= 1)
    )
    """,
    "CREATE INDEX provisioning_runs_status ON platform.provisioning_runs (status)",
    # ---------------------------------------------------------------------------- grants
    # DML only, no DELETE: staff are deactivated, sessions revoked, runs kept as history.
    """
    GRANT SELECT, INSERT, UPDATE ON
        platform.platform_users, platform.platform_recovery_codes, platform.platform_sessions,
        platform.provisioning_runs
        TO platform_app
    """,
]


def upgrade() -> None:
    execute_statements(STATEMENTS)


def downgrade() -> None:
    raise NotImplementedError("migrations only expand (LLD 6.7); roll forward instead")
