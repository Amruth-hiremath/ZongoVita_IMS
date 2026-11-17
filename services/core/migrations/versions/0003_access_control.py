"""Access control: permission catalogue, roles, role permissions, role assignments, access version
(LLD 5.1, section 7; AD-45, AD-46, LD-53, LD-15).

The built-in rules of LLD section 7 that the database can hold are enforced here, whatever the
application does:

- Exactly one super admin (LD-53): a partial unique index on the assignment's derived
  super_admin flag (never two) and a deferred commit-time trigger (never zero; held by a user who
  is invited or active).
- The super_admin flag is copied from the role by trigger; the application cannot set it.
- API clients never hold super-admin rights: CHECK super_admin => principal_type = 'user'.
- Reserved permissions stay with Super Admin, and the Super Admin role cannot be edited: trigger
  on role_permissions. Super Admin holds every permission by definition, so it has no
  role_permissions rows at all (decision I-25).
- The super admin user cannot be suspended or deactivated before a transfer (trigger on users).
- Assignments are revoked, never deleted; a revoked assignment stays revoked.
- Every role, role-permission or assignment change increments iam.access_version in the same
  transaction, which invalidates per-process permission caches (LD-15).

iam.permission_catalog is rebuilt from code (ims_contracts.permissions) after every migration and
the seeded roles are inserted at provisioning, both by the database pipeline (LLD 6.6). The
application role may only read the catalogue and the access version.

role_assignments.site_id gets its foreign key with the organisation module (unit 4), like
iam.users.home_site_id (D-18).

Revision ID: 0003
Revises: 0002
"""

from ims_common.ddl import execute_statements
from ims_core.schema.ddl import app_role

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    app = app_role()
    execute_statements(
        [
            # ------------------------------------------------------------ access version
            """
            CREATE TABLE iam.access_version (
                id         boolean     PRIMARY KEY DEFAULT true,
                version    bigint      NOT NULL,
                changed_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT access_version_single_row CHECK (id),
                CONSTRAINT access_version_positive CHECK (version >= 1)
            )
            """,
            "INSERT INTO iam.access_version (id, version) VALUES (true, 1)",
            f"GRANT SELECT ON iam.access_version TO {app}",
            # Runs as the table owner, so the application needs no write right on the counter.
            """
            CREATE FUNCTION iam.bump_access_version() RETURNS trigger
            LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
            BEGIN
                UPDATE iam.access_version SET version = version + 1, changed_at = now();
                RETURN NULL;
            END $$
            """,
            "REVOKE ALL ON FUNCTION iam.bump_access_version() FROM PUBLIC",
            # -------------------------------------------------------- permission catalogue
            """
            CREATE TABLE iam.permission_catalog (
                code                    text    PRIMARY KEY,
                module                  text    NOT NULL,
                site_scoped             boolean NOT NULL,
                reserved_to_super_admin boolean NOT NULL DEFAULT false,
                CONSTRAINT permission_catalog_code_format
                    CHECK (code ~ '^[a-z_]+\\.[a-z_]+\\.[a-z_]+$'),
                CONSTRAINT permission_catalog_module_matches
                    CHECK (module = split_part(code, '.', 1))
            )
            """,
            f"GRANT SELECT ON iam.permission_catalog TO {app}",
            # ------------------------------------------------------------------------ roles
            """
            CREATE TABLE iam.roles (
                id                        uuid        PRIMARY KEY,
                code                      text        NOT NULL,
                name                      text        NOT NULL,
                description               text,
                kind                      text        NOT NULL,
                user_type_no              smallint,
                is_super_admin_equivalent boolean     NOT NULL DEFAULT false,
                created_at                timestamptz NOT NULL DEFAULT now(),
                created_by                uuid,
                updated_at                timestamptz NOT NULL DEFAULT now(),
                updated_by                uuid,
                version                   integer     NOT NULL DEFAULT 1,
                CONSTRAINT roles_code_key UNIQUE (code),
                CONSTRAINT roles_code_format CHECK (code ~ '^[a-z][a-z0-9_]{1,62}$'),
                CONSTRAINT roles_name_present CHECK (btrim(name) <> '' AND length(name) <= 100),
                CONSTRAINT roles_kind_check CHECK (kind IN ('user_type', 'super_admin', 'custom')),
                CONSTRAINT roles_user_type_numbered CHECK ((kind = 'user_type') = (user_type_no IS NOT NULL)),
                CONSTRAINT roles_user_type_range CHECK (user_type_no BETWEEN 1 AND 4),
                CONSTRAINT roles_super_admin_flag CHECK (is_super_admin_equivalent = (kind = 'super_admin')),
                CONSTRAINT roles_version_positive CHECK (version >= 1)
            )
            """,
            # The super-admin flag is authoritative and unique (LLD 5.1); one role per user type.
            """
            CREATE UNIQUE INDEX roles_one_super_admin ON iam.roles (is_super_admin_equivalent)
                WHERE is_super_admin_equivalent
            """,
            """
            CREATE UNIQUE INDEX roles_user_type_no_key ON iam.roles (user_type_no)
                WHERE user_type_no IS NOT NULL
            """,
            """
            CREATE FUNCTION iam.roles_guard() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.kind = 'super_admin' THEN
                    RAISE EXCEPTION 'iam.roles: the Super Admin role cannot be edited'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                IF NEW.id <> OLD.id OR NEW.code <> OLD.code OR NEW.kind <> OLD.kind
                   OR NEW.user_type_no IS DISTINCT FROM OLD.user_type_no
                   OR NEW.is_super_admin_equivalent <> OLD.is_super_admin_equivalent THEN
                    RAISE EXCEPTION 'iam.roles: id, code, kind and user type of a role never change'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                RETURN NEW;
            END $$
            """,
            """
            CREATE TRIGGER roles_guard BEFORE UPDATE ON iam.roles
                FOR EACH ROW EXECUTE FUNCTION iam.roles_guard()
            """,
            """
            CREATE TRIGGER roles_access_version AFTER INSERT OR UPDATE OR DELETE ON iam.roles
                FOR EACH STATEMENT EXECUTE FUNCTION iam.bump_access_version()
            """,
            f"GRANT SELECT, INSERT, UPDATE ON iam.roles TO {app}",
            # ------------------------------------------------------------- role permissions
            """
            CREATE TABLE iam.role_permissions (
                role_id         uuid        NOT NULL REFERENCES iam.roles (id),
                permission_code text        NOT NULL REFERENCES iam.permission_catalog (code),
                granted_at      timestamptz NOT NULL DEFAULT now(),
                granted_by      uuid,
                CONSTRAINT role_permissions_pkey PRIMARY KEY (role_id, permission_code)
            )
            """,
            "CREATE INDEX role_permissions_code ON iam.role_permissions (permission_code)",
            """
            CREATE FUNCTION iam.role_permissions_guard() RETURNS trigger
            LANGUAGE plpgsql AS $$
            DECLARE
                target_role uuid := CASE WHEN TG_OP = 'DELETE' THEN OLD.role_id ELSE NEW.role_id END;
            BEGIN
                IF EXISTS (SELECT 1 FROM iam.roles WHERE id = target_role AND kind = 'super_admin')
                   OR (TG_OP = 'UPDATE' AND EXISTS (
                       SELECT 1 FROM iam.roles WHERE id = OLD.role_id AND kind = 'super_admin')) THEN
                    RAISE EXCEPTION
                        'iam.role_permissions: the Super Admin role holds every permission, not editable'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                IF TG_OP <> 'DELETE' AND EXISTS (
                    SELECT 1 FROM iam.permission_catalog
                     WHERE code = NEW.permission_code AND reserved_to_super_admin
                ) THEN
                    RAISE EXCEPTION 'iam.role_permissions: % is reserved to the Super Admin role',
                        NEW.permission_code USING ERRCODE = 'insufficient_privilege';
                END IF;
                RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
            END $$
            """,
            """
            CREATE TRIGGER role_permissions_guard BEFORE INSERT OR UPDATE OR DELETE ON iam.role_permissions
                FOR EACH ROW EXECUTE FUNCTION iam.role_permissions_guard()
            """,
            """
            CREATE TRIGGER role_permissions_access_version
                AFTER INSERT OR UPDATE OR DELETE ON iam.role_permissions
                FOR EACH STATEMENT EXECUTE FUNCTION iam.bump_access_version()
            """,
            # On the DELETE exception list (LLD section 3): removing a permission from a role.
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON iam.role_permissions TO {app}",
            # ------------------------------------------------------------- role assignments
            """
            CREATE TABLE iam.role_assignments (
                id             uuid        PRIMARY KEY,
                principal_type text        NOT NULL,
                principal_id   uuid        NOT NULL,
                role_id        uuid        NOT NULL REFERENCES iam.roles (id),
                site_id        uuid,
                super_admin    boolean     NOT NULL DEFAULT false,
                granted_at     timestamptz NOT NULL DEFAULT now(),
                granted_by     uuid,
                revoked_at     timestamptz,
                revoked_by     uuid,
                revoke_reason  text,
                CONSTRAINT role_assignments_principal_type_check
                    CHECK (principal_type IN ('user', 'api_client')),
                CONSTRAINT role_assignments_super_admin_is_user
                    CHECK (NOT super_admin OR principal_type = 'user'),
                CONSTRAINT role_assignments_super_admin_all_sites
                    CHECK (NOT super_admin OR site_id IS NULL),
                CONSTRAINT role_assignments_revocation
                    CHECK (revoked_at IS NOT NULL OR (revoked_by IS NULL AND revoke_reason IS NULL)),
                CONSTRAINT role_assignments_revoked_after_granted
                    CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
            )
            """,
            # Never two super admins (LD-53).
            """
            CREATE UNIQUE INDEX role_assignments_one_super_admin ON iam.role_assignments (super_admin)
                WHERE super_admin AND revoked_at IS NULL
            """,
            """
            CREATE UNIQUE INDEX role_assignments_active_key
                ON iam.role_assignments (principal_type, principal_id, role_id, site_id) NULLS NOT DISTINCT
                WHERE revoked_at IS NULL
            """,
            """
            CREATE INDEX role_assignments_principal ON iam.role_assignments (principal_id)
                WHERE revoked_at IS NULL
            """,
            "CREATE INDEX role_assignments_role ON iam.role_assignments (role_id) WHERE revoked_at IS NULL",
            """
            CREATE FUNCTION iam.role_assignments_before_insert() RETURNS trigger
            LANGUAGE plpgsql AS $$
            DECLARE
                principal_status text;
            BEGIN
                -- The flag is derived from the role, never supplied (LLD 5.1).
                NEW.super_admin := coalesce(
                    (SELECT is_super_admin_equivalent FROM iam.roles WHERE id = NEW.role_id), false);
                IF NEW.principal_type = 'user' THEN
                    -- FOR SHARE conflicts with a concurrent status change of the same user.
                    SELECT status INTO principal_status FROM iam.users WHERE id = NEW.principal_id FOR SHARE;
                ELSE
                    SELECT status INTO principal_status FROM iam.api_clients WHERE id = NEW.principal_id;
                END IF;
                IF principal_status IS NULL THEN
                    RAISE EXCEPTION 'iam.role_assignments: no % with id %',
                        NEW.principal_type, NEW.principal_id USING ERRCODE = 'foreign_key_violation';
                END IF;
                IF NEW.super_admin AND principal_status NOT IN ('invited', 'active') THEN
                    RAISE EXCEPTION 'iam.role_assignments: the super admin must be an invited or active user'
                        USING ERRCODE = 'integrity_constraint_violation';
                END IF;
                RETURN NEW;
            END $$
            """,
            """
            CREATE TRIGGER role_assignments_before_insert BEFORE INSERT ON iam.role_assignments
                FOR EACH ROW EXECUTE FUNCTION iam.role_assignments_before_insert()
            """,
            """
            CREATE FUNCTION iam.role_assignments_revoke_only() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.id <> OLD.id OR NEW.principal_type <> OLD.principal_type
                   OR NEW.principal_id <> OLD.principal_id OR NEW.role_id <> OLD.role_id
                   OR NEW.site_id IS DISTINCT FROM OLD.site_id OR NEW.super_admin <> OLD.super_admin
                   OR NEW.granted_at <> OLD.granted_at OR NEW.granted_by IS DISTINCT FROM OLD.granted_by THEN
                    RAISE EXCEPTION 'iam.role_assignments: an assignment can only be revoked'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                IF OLD.revoked_at IS NOT NULL THEN
                    RAISE EXCEPTION 'iam.role_assignments: a revoked assignment stays revoked'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                RETURN NEW;
            END $$
            """,
            """
            CREATE TRIGGER role_assignments_revoke_only BEFORE UPDATE ON iam.role_assignments
                FOR EACH ROW EXECUTE FUNCTION iam.role_assignments_revoke_only()
            """,
            # Never zero super admins, checked when the transaction commits (LD-53).
            """
            CREATE FUNCTION iam.role_assignments_one_super_admin() RETURNS trigger
            LANGUAGE plpgsql AS $$
            DECLARE
                holders integer;
            BEGIN
                SELECT count(*) INTO holders
                  FROM iam.role_assignments ra
                  JOIN iam.users u ON u.id = ra.principal_id
                 WHERE ra.super_admin AND ra.revoked_at IS NULL AND ra.principal_type = 'user'
                   AND u.status IN ('invited', 'active');
                IF holders <> 1 THEN
                    RAISE EXCEPTION
                        'iam.role_assignments: exactly one super admin, an invited or active user (found %)',
                        holders USING ERRCODE = 'integrity_constraint_violation';
                END IF;
                RETURN NULL;
            END $$
            """,
            """
            CREATE CONSTRAINT TRIGGER role_assignments_super_admin_inserted
                AFTER INSERT ON iam.role_assignments DEFERRABLE INITIALLY DEFERRED
                FOR EACH ROW WHEN (NEW.super_admin)
                EXECUTE FUNCTION iam.role_assignments_one_super_admin()
            """,
            """
            CREATE CONSTRAINT TRIGGER role_assignments_super_admin_changed
                AFTER UPDATE ON iam.role_assignments DEFERRABLE INITIALLY DEFERRED
                FOR EACH ROW WHEN (OLD.super_admin OR NEW.super_admin)
                EXECUTE FUNCTION iam.role_assignments_one_super_admin()
            """,
            """
            CREATE TRIGGER role_assignments_access_version
                AFTER INSERT OR UPDATE OR DELETE ON iam.role_assignments
                FOR EACH STATEMENT EXECUTE FUNCTION iam.bump_access_version()
            """,
            f"GRANT SELECT, INSERT, UPDATE ON iam.role_assignments TO {app}",
            # ------------------------------------------------- no lock-out of the super admin
            """
            CREATE FUNCTION iam.users_super_admin_guard() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.status IN ('suspended', 'deactivated') AND NEW.status IS DISTINCT FROM OLD.status
                   AND EXISTS (
                       SELECT 1 FROM iam.role_assignments
                        WHERE principal_type = 'user' AND principal_id = OLD.id
                          AND super_admin AND revoked_at IS NULL
                   ) THEN
                    RAISE EXCEPTION
                        'iam.users: the super admin cannot be suspended or deactivated before a transfer'
                        USING ERRCODE = 'integrity_constraint_violation';
                END IF;
                RETURN NEW;
            END $$
            """,
            """
            CREATE TRIGGER users_super_admin_guard BEFORE UPDATE OF status ON iam.users
                FOR EACH ROW EXECUTE FUNCTION iam.users_super_admin_guard()
            """,
        ]
    )


def downgrade() -> None:
    raise NotImplementedError("migrations only expand (LLD 6.7); roll forward instead")
