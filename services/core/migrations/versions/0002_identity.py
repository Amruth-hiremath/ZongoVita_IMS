"""Identity: users, MFA factors and recovery codes, sessions, API clients (LLD 5.1, 6.2, 6.3).

Columns follow LLD 5.1. Additions, each needed by a flow the LLD describes:
- iam.users.activation_code_hash / activation_expires_at: the one-time activation code new users
  receive until an email channel exists (LLD 6.2, #21).
- iam.users.mfa_challenge_jti / mfa_challenge_expires_at: makes the MFA challenge token single use
  (LLD 6.2) without a separate table.
- iam.mfa_factors.secret_key_id, revoked_at: the key that encrypts the TOTP secret (rotation), and
  replacing an unconfirmed enrolment without deleting it.
- iam.sessions.last_refreshed_at, revoke_reason.

department_id and home_site_id get their foreign keys with the organisation module (unit 4).
iam.sessions.user_id has no foreign key: support sessions (LD-83, unit 12) are for support
principals, who are not rows of iam.users.

Revision ID: 0002
Revises: 0001
"""

from ims_common.ddl import execute_statements
from ims_core.schema.ddl import app_role

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    app = app_role()
    execute_statements(
        [
            # ---------------------------------------------------------------------- users
            """
            CREATE TABLE iam.users (
                id                       uuid        PRIMARY KEY,
                login_identifier         text        NOT NULL,
                display_name             text        NOT NULL,
                email                    text,
                department_id            uuid,
                home_site_id             uuid,
                status                   text        NOT NULL DEFAULT 'invited',
                password_hash            text,
                failed_attempts          integer     NOT NULL DEFAULT 0,
                locked_until             timestamptz,
                mfa_enrolled_at          timestamptz,
                mfa_challenge_jti        text,
                mfa_challenge_expires_at timestamptz,
                activation_code_hash     bytea,
                activation_expires_at    timestamptz,
                created_at               timestamptz NOT NULL DEFAULT now(),
                created_by               uuid,
                updated_at               timestamptz NOT NULL DEFAULT now(),
                updated_by               uuid,
                version                  integer     NOT NULL DEFAULT 1,
                CONSTRAINT users_login_identifier_key UNIQUE (login_identifier),
                CONSTRAINT users_login_identifier_trimmed
                    CHECK (login_identifier = btrim(login_identifier) AND login_identifier <> ''),
                CONSTRAINT users_display_name_present CHECK (btrim(display_name) <> ''),
                CONSTRAINT users_status_check
                    CHECK (status IN ('invited', 'active', 'suspended', 'deactivated')),
                CONSTRAINT users_active_has_password CHECK (status <> 'active' OR password_hash IS NOT NULL),
                CONSTRAINT users_failed_attempts_range CHECK (failed_attempts >= 0),
                CONSTRAINT users_challenge_pair
                    CHECK ((mfa_challenge_jti IS NULL) = (mfa_challenge_expires_at IS NULL)),
                CONSTRAINT users_activation_pair
                    CHECK ((activation_code_hash IS NULL) = (activation_expires_at IS NULL)),
                CONSTRAINT users_activation_hash_length
                    CHECK (activation_code_hash IS NULL OR octet_length(activation_code_hash) = 32),
                CONSTRAINT users_version_positive CHECK (version >= 1)
            )
            """,
            "CREATE INDEX users_status ON iam.users (status)",
            f"GRANT SELECT, INSERT, UPDATE ON iam.users TO {app}",
            # ------------------------------------------------------------------- MFA factors
            """
            CREATE TABLE iam.mfa_factors (
                id                uuid        PRIMARY KEY,
                user_id           uuid        NOT NULL REFERENCES iam.users (id),
                kind              text        NOT NULL DEFAULT 'totp',
                secret_ciphertext bytea       NOT NULL,
                secret_key_id     text        NOT NULL,
                enrolled_at       timestamptz,
                last_used_step    bigint,
                revoked_at        timestamptz,
                created_at        timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT mfa_factors_kind_check CHECK (kind IN ('totp')),
                CONSTRAINT mfa_factors_step_after_enrolment
                    CHECK (last_used_step IS NULL OR enrolled_at IS NOT NULL)
            )
            """,
            # One active factor per user (LLD 5.1), and at most one enrolment in progress.
            """
            CREATE UNIQUE INDEX mfa_factors_one_active ON iam.mfa_factors (user_id)
                WHERE enrolled_at IS NOT NULL AND revoked_at IS NULL
            """,
            """
            CREATE UNIQUE INDEX mfa_factors_one_pending ON iam.mfa_factors (user_id)
                WHERE enrolled_at IS NULL AND revoked_at IS NULL
            """,
            f"GRANT SELECT, INSERT, UPDATE ON iam.mfa_factors TO {app}",
            # ---------------------------------------------------------------- recovery codes
            """
            CREATE TABLE iam.mfa_recovery_codes (
                id         uuid        PRIMARY KEY,
                user_id    uuid        NOT NULL REFERENCES iam.users (id),
                code_hash  bytea       NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                used_at    timestamptz,
                revoked_at timestamptz,
                CONSTRAINT mfa_recovery_codes_hash_length CHECK (octet_length(code_hash) = 32),
                CONSTRAINT mfa_recovery_codes_user_code_key UNIQUE (user_id, code_hash)
            )
            """,
            f"GRANT SELECT, INSERT, UPDATE ON iam.mfa_recovery_codes TO {app}",
            # ----------------------------------------------------------------------- sessions
            """
            CREATE TABLE iam.sessions (
                id                  uuid        PRIMARY KEY,
                user_id             uuid        NOT NULL,
                principal_type      text        NOT NULL DEFAULT 'user',
                current_refresh_jti text        NOT NULL,
                mfa_verified_at     timestamptz NOT NULL,
                support_grant_id    uuid,
                created_at          timestamptz NOT NULL DEFAULT now(),
                last_refreshed_at   timestamptz NOT NULL,
                idle_expires_at     timestamptz NOT NULL,
                absolute_expires_at timestamptz NOT NULL,
                revoked_at          timestamptz,
                revoke_reason       text,
                CONSTRAINT sessions_principal_type_check CHECK (principal_type IN ('user', 'support')),
                CONSTRAINT sessions_support_has_grant
                    CHECK ((principal_type = 'support') = (support_grant_id IS NOT NULL)),
                CONSTRAINT sessions_idle_within_absolute CHECK (idle_expires_at <= absolute_expires_at),
                CONSTRAINT sessions_revoke_pair CHECK ((revoked_at IS NULL) = (revoke_reason IS NULL))
            )
            """,
            "CREATE INDEX sessions_user ON iam.sessions (user_id) WHERE revoked_at IS NULL",
            "CREATE INDEX sessions_absolute_expiry ON iam.sessions (absolute_expires_at)",
            # On the DELETE exception list (LLD section 3), but only past absolute expiry.
            """
            CREATE FUNCTION iam.sessions_delete_guard() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.absolute_expires_at > now() THEN
                    RAISE EXCEPTION 'iam.sessions: only sessions past their absolute expiry may be deleted'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                RETURN OLD;
            END $$
            """,
            """
            CREATE TRIGGER sessions_delete_guard BEFORE DELETE ON iam.sessions
                FOR EACH ROW EXECUTE FUNCTION iam.sessions_delete_guard()
            """,
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON iam.sessions TO {app}",
            # -------------------------------------------------------------------- API clients
            """
            CREATE TABLE iam.api_clients (
                id                    uuid        PRIMARY KEY,
                name                  text        NOT NULL,
                secret_hash           bytea       NOT NULL,
                rate_limit_per_minute integer     NOT NULL DEFAULT 600,
                status                text        NOT NULL DEFAULT 'active',
                created_at            timestamptz NOT NULL DEFAULT now(),
                created_by            uuid,
                updated_at            timestamptz NOT NULL DEFAULT now(),
                updated_by            uuid,
                version               integer     NOT NULL DEFAULT 1,
                CONSTRAINT api_clients_name_present CHECK (btrim(name) <> ''),
                CONSTRAINT api_clients_secret_hash_length CHECK (octet_length(secret_hash) = 32),
                CONSTRAINT api_clients_rate_limit_positive CHECK (rate_limit_per_minute > 0),
                CONSTRAINT api_clients_status_check CHECK (status IN ('active', 'disabled')),
                CONSTRAINT api_clients_version_positive CHECK (version >= 1)
            )
            """,
            f"GRANT SELECT, INSERT, UPDATE ON iam.api_clients TO {app}",
        ]
    )


def downgrade() -> None:
    raise NotImplementedError("migrations only expand (LLD 6.7); roll forward instead")
