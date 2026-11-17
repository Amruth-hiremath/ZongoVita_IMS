-- Pooler authentication lookup (LLD 6.5: "each customer role is authenticated through the
-- pooler's auth query"). Runs once when the local cluster is initialised.
--
-- PgBouncer logs in as pgbouncer_auth and calls pgbouncer.get_auth(<user>) in the postgres
-- database to obtain the SCRAM verifier of the connecting role. Only roles that are meant to
-- reach PostgreSQL through the pooler are resolvable: per-customer application roles,
-- per-customer break-glass roles and the Platform Service role. Migration roles and
-- superusers are deliberately absent, so they cannot be used through the pooler at all.

CREATE ROLE pgbouncer_auth LOGIN PASSWORD 'ims_local_pooler';

CREATE SCHEMA pgbouncer;

CREATE FUNCTION pgbouncer.get_auth(p_usename text)
RETURNS TABLE (usename name, passwd text)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
    SELECT s.usename, s.passwd
      FROM pg_catalog.pg_shadow s
     WHERE s.usename = p_usename
       AND (s.usename ~ '^ims_(app|breakglass)_[a-z0-9_]+$' OR s.usename = 'platform_app');
$$;

REVOKE ALL ON SCHEMA pgbouncer FROM PUBLIC;
REVOKE ALL ON FUNCTION pgbouncer.get_auth(text) FROM PUBLIC;
GRANT USAGE ON SCHEMA pgbouncer TO pgbouncer_auth;
GRANT EXECUTE ON FUNCTION pgbouncer.get_auth(text) TO pgbouncer_auth;
