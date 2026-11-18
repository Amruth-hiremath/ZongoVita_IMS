"""Organisation: sites, locations, departments (LLD 5.1); keys from identity and access to them.

Rules held by the database:

- Site status is staged, active or inactive, and moves only along staged -> active,
  staged -> inactive, active -> inactive, inactive -> active (decision D-28).
- A site's timezone is an IANA name PostgreSQL knows (LLD 3: "each site stores an IANA timezone").
- Exactly one default location per site (LLD 5.1): a partial unique index (never two) and a
  deferred commit-time trigger (never none, including for a new site).
- The default location is active; a location never moves to another site.
- Site, location and department codes are unique per customer, ignoring case.
- Nothing is deleted: sites, locations and departments are deactivated.

The licence site limit (staged and active sites, AD-27) is checked by the service under a
transaction-level advisory lock, as the user limit is: the limit lives in the licence snapshot,
not in the customer database.

iam.users.department_id, iam.users.home_site_id and iam.role_assignments.site_id get their
foreign keys here (D-18, D-21): added NOT VALID, then validated (LLD 6.7).

Revision ID: 0004
Revises: 0003
"""

from ims_common.ddl import execute_statements
from ims_core.schema.ddl import app_role

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_AUDIT_COLUMNS = """
                created_at  timestamptz NOT NULL DEFAULT now(),
                created_by  uuid,
                updated_at  timestamptz NOT NULL DEFAULT now(),
                updated_by  uuid,
                version     integer     NOT NULL DEFAULT 1"""


def upgrade() -> None:
    app = app_role()
    execute_statements(
        [
            # ------------------------------------------------------------------------ sites
            f"""
            CREATE TABLE org.sites (
                id          uuid        PRIMARY KEY,
                code        text        NOT NULL,
                name        text        NOT NULL,
                timezone    text        NOT NULL,
                status      text        NOT NULL DEFAULT 'staged',{_AUDIT_COLUMNS},
                CONSTRAINT sites_code_format CHECK (code ~ '^[A-Za-z0-9][A-Za-z0-9._-]{{0,31}}$'),
                CONSTRAINT sites_name_present CHECK (btrim(name) <> '' AND length(name) <= 200),
                CONSTRAINT sites_status_check CHECK (status IN ('staged', 'active', 'inactive')),
                CONSTRAINT sites_version_positive CHECK (version >= 1)
            )
            """,
            "CREATE UNIQUE INDEX sites_code_key ON org.sites (upper(code))",
            "CREATE INDEX sites_status ON org.sites (status)",
            """
            CREATE FUNCTION org.sites_guard() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_timezone_names WHERE name = NEW.timezone) THEN
                    RAISE EXCEPTION 'org.sites: % is not a known IANA timezone', NEW.timezone
                        USING ERRCODE = 'check_violation';
                END IF;
                IF TG_OP = 'UPDATE' THEN
                    IF NEW.id <> OLD.id OR NEW.code <> OLD.code THEN
                        RAISE EXCEPTION 'org.sites: the id and code of a site never change'
                            USING ERRCODE = 'insufficient_privilege';
                    END IF;
                    IF NEW.status <> OLD.status AND (OLD.status, NEW.status) NOT IN (
                        ('staged', 'active'), ('staged', 'inactive'),
                        ('active', 'inactive'), ('inactive', 'active')
                    ) THEN
                        RAISE EXCEPTION 'org.sites: % -> % is not a site transition', OLD.status, NEW.status
                            USING ERRCODE = 'check_violation';
                    END IF;
                END IF;
                RETURN NEW;
            END $$
            """,
            """
            CREATE TRIGGER sites_guard BEFORE INSERT OR UPDATE ON org.sites
                FOR EACH ROW EXECUTE FUNCTION org.sites_guard()
            """,
            f"GRANT SELECT, INSERT, UPDATE ON org.sites TO {app}",
            # -------------------------------------------------------------------- locations
            f"""
            CREATE TABLE org.locations (
                id          uuid        PRIMARY KEY,
                site_id     uuid        NOT NULL REFERENCES org.sites (id),
                code        text        NOT NULL,
                name        text        NOT NULL,
                is_default  boolean     NOT NULL DEFAULT false,
                status      text        NOT NULL DEFAULT 'active',{_AUDIT_COLUMNS},
                CONSTRAINT locations_code_format CHECK (code ~ '^[A-Za-z0-9][A-Za-z0-9._-]{{0,31}}$'),
                CONSTRAINT locations_name_present CHECK (btrim(name) <> '' AND length(name) <= 200),
                CONSTRAINT locations_status_check CHECK (status IN ('active', 'inactive')),
                CONSTRAINT locations_default_is_active CHECK (NOT is_default OR status = 'active'),
                CONSTRAINT locations_version_positive CHECK (version >= 1)
            )
            """,
            "CREATE UNIQUE INDEX locations_code_key ON org.locations (upper(code))",
            "CREATE INDEX locations_site ON org.locations (site_id)",
            # Never two defaults per site.
            "CREATE UNIQUE INDEX locations_one_default ON org.locations (site_id) WHERE is_default",
            """
            CREATE FUNCTION org.locations_guard() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.id <> OLD.id OR NEW.site_id <> OLD.site_id OR NEW.code <> OLD.code THEN
                    RAISE EXCEPTION 'org.locations: the id, site and code of a location never change'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                RETURN NEW;
            END $$
            """,
            """
            CREATE TRIGGER locations_guard BEFORE UPDATE ON org.locations
                FOR EACH ROW EXECUTE FUNCTION org.locations_guard()
            """,
            # Never none: checked when the transaction commits, for the site of every new site row
            # and every inserted or changed location.
            """
            CREATE FUNCTION org.site_has_one_default() RETURNS trigger
            LANGUAGE plpgsql AS $$
            DECLARE
                target uuid;
                defaults integer;
            BEGIN
                -- Each statement is prepared when it runs, so NEW.site_id is only read for locations.
                IF TG_TABLE_NAME = 'sites' THEN
                    target := NEW.id;
                ELSE
                    target := NEW.site_id;
                END IF;
                SELECT count(*) INTO defaults FROM org.locations WHERE site_id = target AND is_default;
                IF defaults <> 1 THEN
                    RAISE EXCEPTION 'org.locations: site % must have exactly one default location (found %)',
                        target, defaults USING ERRCODE = 'integrity_constraint_violation';
                END IF;
                RETURN NULL;
            END $$
            """,
            """
            CREATE CONSTRAINT TRIGGER sites_have_default_location
                AFTER INSERT ON org.sites DEFERRABLE INITIALLY DEFERRED
                FOR EACH ROW EXECUTE FUNCTION org.site_has_one_default()
            """,
            """
            CREATE CONSTRAINT TRIGGER locations_one_default_per_site
                AFTER INSERT OR UPDATE ON org.locations DEFERRABLE INITIALLY DEFERRED
                FOR EACH ROW EXECUTE FUNCTION org.site_has_one_default()
            """,
            f"GRANT SELECT, INSERT, UPDATE ON org.locations TO {app}",
            # ------------------------------------------------------------------ departments
            f"""
            CREATE TABLE org.departments (
                id          uuid        PRIMARY KEY,
                code        text        NOT NULL,
                name        text        NOT NULL,
                status      text        NOT NULL DEFAULT 'active',{_AUDIT_COLUMNS},
                CONSTRAINT departments_code_format CHECK (code ~ '^[A-Za-z0-9][A-Za-z0-9._-]{{0,31}}$'),
                CONSTRAINT departments_name_present CHECK (btrim(name) <> '' AND length(name) <= 200),
                CONSTRAINT departments_status_check CHECK (status IN ('active', 'inactive')),
                CONSTRAINT departments_version_positive CHECK (version >= 1)
            )
            """,
            "CREATE UNIQUE INDEX departments_code_key ON org.departments (upper(code))",
            """
            CREATE FUNCTION org.departments_guard() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.id <> OLD.id OR NEW.code <> OLD.code THEN
                    RAISE EXCEPTION 'org.departments: the id and code of a department never change'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                RETURN NEW;
            END $$
            """,
            """
            CREATE TRIGGER departments_guard BEFORE UPDATE ON org.departments
                FOR EACH ROW EXECUTE FUNCTION org.departments_guard()
            """,
            f"GRANT SELECT, INSERT, UPDATE ON org.departments TO {app}",
            # ------------------------------------------- keys from identity and access (D-18, D-21)
            """
            ALTER TABLE iam.users ADD CONSTRAINT users_department_fk
                FOREIGN KEY (department_id) REFERENCES org.departments (id) NOT VALID
            """,
            "ALTER TABLE iam.users VALIDATE CONSTRAINT users_department_fk",
            """
            ALTER TABLE iam.users ADD CONSTRAINT users_home_site_fk
                FOREIGN KEY (home_site_id) REFERENCES org.sites (id) NOT VALID
            """,
            "ALTER TABLE iam.users VALIDATE CONSTRAINT users_home_site_fk",
            """
            ALTER TABLE iam.role_assignments ADD CONSTRAINT role_assignments_site_fk
                FOREIGN KEY (site_id) REFERENCES org.sites (id) NOT VALID
            """,
            "ALTER TABLE iam.role_assignments VALIDATE CONSTRAINT role_assignments_site_fk",
            "CREATE INDEX users_department ON iam.users (department_id) WHERE department_id IS NOT NULL",
            "CREATE INDEX users_home_site ON iam.users (home_site_id) WHERE home_site_id IS NOT NULL",
            "CREATE INDEX role_assignments_site ON iam.role_assignments (site_id) WHERE site_id IS NOT NULL",
        ]
    )


def downgrade() -> None:
    raise NotImplementedError("migrations only expand (LLD 6.7); roll forward instead")
