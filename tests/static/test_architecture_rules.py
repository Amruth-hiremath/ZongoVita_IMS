"""Static CI checks (LD-01, LD-62, LD-75; LLD section 17 "Tenant context, permissions ...").

Each rule is first shown to catch a violation in a small synthetic tree, then applied to the
real source tree.
"""

from __future__ import annotations

from pathlib import Path

import ims_core
import ims_platform
from ims_common.problem import ERROR_CATALOGUE
from ims_contracts.errors import ErrorCode
from tests.static import rules


def _write(root: Path, files: dict[str, str]) -> Path:
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return root


# ------------------------------------------------------------------------------ module rules
def test_boundary_rule_catches_violations(tmp_path: Path) -> None:
    core = _write(
        tmp_path / "ims_core",
        {
            "kernel/uow.py": "from ims_core.modules.catalogue import service\n",
            "schema/access.py": "import ims_core.modules.inventory.repository\n",
            "modules/catalogue/service.py": (
                "from ims_core.kernel.uow import UnitOfWork\n"
                "from ims_core.modules.catalogue import repository\n"
                "from . import domain\n"
                "from .schemas import ItemIn\n"
                "from ims_core.modules.inventory.public import free_stock\n"
                "from ims_core.modules.inventory import public\n"
                "from ims_core.modules.inventory import repository as stock_sql\n"
                "from ims_core.modules.inventory.service import reserve\n"
                "from ..purchasing.domain import VendorStatus\n"
            ),
        },
    )
    violations = [str(v) for v in rules.core_boundary_violations(core)]
    assert len(violations) == 5, violations
    assert any("kernel/uow.py" in v and "kernel must not import" in v for v in violations)
    assert any("schema/access.py" in v for v in violations)
    assert any("inventory.repository" in v for v in violations)
    assert any("inventory.service" in v for v in violations)
    assert any("purchasing.domain" in v for v in violations), "relative imports are resolved"


def test_core_respects_module_boundaries() -> None:
    assert rules.core_boundary_violations() == []


def test_deployables_do_not_import_each_other() -> None:
    """Split only at trust or lifecycle boundaries, and keep those boundaries real (AD-01)."""
    checks = [
        (
            rules.CONTRACTS,
            "ims_contracts",
            ("ims_common", "ims_core", "ims_platform", "ims_db_pipeline", "fastapi", "sqlalchemy"),
        ),
        (rules.COMMON, "ims_common", ("ims_core", "ims_platform", "ims_db_pipeline")),
        # Core never runs DDL and never reaches into the Platform Service's code or database.
        (rules.CORE, "ims_core", ("ims_platform", "ims_db_pipeline")),
        # The platform tier has no code path into customer data (AD-13).
        (rules.PLATFORM, "ims_platform", ("ims_core", "ims_db_pipeline")),
    ]
    for root, package, forbidden in checks:
        assert rules.forbidden_import_violations(root, package, forbidden) == [], package


def test_deployable_rule_catches_violations(tmp_path: Path) -> None:
    root = _write(
        tmp_path / "ims_platform", {"registry.py": "from ims_core.kernel import db\nimport ims_db_pipeline\n"}
    )
    assert len(rules.forbidden_import_violations(root, "ims_platform", ("ims_core", "ims_db_pipeline"))) == 2


# ----------------------------------------------------- sessions only through tenant context
def test_engine_rule_catches_violations(tmp_path: Path) -> None:
    core = _write(
        tmp_path / "ims_core",
        {
            "kernel/db.py": "from ims_common.pg import create_pooler_engine\n",
            "modules/reporting/repository.py": (
                "from sqlalchemy.ext.asyncio import create_async_engine\n"
                "import sqlalchemy\n"
                "engine = sqlalchemy.create_engine('postgresql://other-customer')\n"
            ),
            "modules/reporting/service.py": (
                "from ims_core.kernel.context import TenantContext\n"
                "def fake(snapshot):\n"
                "    return TenantContext(customer_id=1, snapshot=snapshot)\n"
            ),
        },
    )
    assert len(rules.engine_creation_violations(core)) == 2
    assert len(rules.tenant_context_construction_violations(core)) == 1


def test_only_the_router_creates_engines_and_only_the_kernel_builds_contexts() -> None:
    assert rules.engine_creation_violations() == []
    assert rules.tenant_context_construction_violations() == []


# -------------------------------------------------------------------- pooler compatibility
def test_pooler_rule_catches_session_state(tmp_path: Path) -> None:
    root = _write(
        tmp_path / "src",
        {
            "bad.py": (
                "A = 'SET statement_timeout = 0'\n"
                "B = 'SELECT pg_advisory_lock(42)'\n"
                "C = 'LISTEN work_pending'\n"
                "D = 'SELECT pg_notify(\\'jobs\\', \\'1\\')'\n"
                "E = 'CREATE TEMP TABLE scratch (id int)'\n"
            ),
            "good.py": (
                "A = 'SET LOCAL lock_timeout = \\'3s\\''\n"
                "B = 'SET TRANSACTION READ ONLY'\n"
                "C = 'SELECT pg_advisory_xact_lock(42)'\n"
                "D = 'UPDATE config.settings SET value = 1'\n"
                "E = 'the worker should listen for hints'\n"
            ),
        },
    )
    violations = rules.pooler_compatibility_violations(root)
    assert sorted({v.file for v in violations}) == ["bad.py"]
    assert len(violations) == 5


def test_application_sql_keeps_no_session_state() -> None:
    """LD-75. The pipeline is exempt: it connects directly, never through the pooler."""
    for root in (rules.CORE, rules.PLATFORM, rules.COMMON, rules.CONTRACTS):
        assert rules.pooler_compatibility_violations(root) == [], root.name


def test_migrations_keep_no_session_state_either() -> None:
    for versions in (ims_core.migrations_path() / "versions", ims_platform.migrations_path() / "versions"):
        assert rules.pooler_compatibility_violations(versions) == []


# -------------------------------------------------------------------------- migration rules
def test_migration_rule_catches_contracting_changes(tmp_path: Path) -> None:
    # Prose in a docstring is not SQL and must not trip the rule.
    header = '"""DROP TABLE the old one and RENAME TO something."""\n'
    versions = _write(
        tmp_path / "versions",
        {
            "0009_bad.py": header
            + (
                "S = ['ALTER TABLE config.settings DROP COLUMN value',\n"
                "     'ALTER TABLE config.settings RENAME TO prefs',\n"
                "     'DROP TABLE audit.audit_log']\n"
                "def upgrade():\n    pass\n"
                "def downgrade():\n    pass\n"
            ),
            "0010_good.py": header
            + (
                "S = ['ALTER TABLE config.settings ADD COLUMN note text',\n"
                "     'CREATE TRIGGER t BEFORE UPDATE OR DELETE ON x.y FOR EACH ROW EXECUTE FUNCTION f()']\n"
                "def upgrade():\n    pass\n"
                "def downgrade():\n    raise NotImplementedError\n"
            ),
        },
    )
    violations = rules.migration_violations(versions)
    assert sorted({v.file for v in violations}) == ["0009_bad.py"]
    assert len(violations) == 4  # three contracting statements and a permissive downgrade


def test_migrations_only_expand_and_never_downgrade() -> None:
    for versions in (ims_core.migrations_path() / "versions", ims_platform.migrations_path() / "versions"):
        assert list(rules.python_files(versions)), versions
        assert rules.migration_violations(versions) == []


# --------------------------------------------------------------------------------- catalogue
def test_every_error_code_has_one_status_and_title() -> None:
    assert set(ERROR_CATALOGUE) == set(ErrorCode)
    by_status: dict[int, set[str]] = {}
    for code, (status, title) in ERROR_CATALOGUE.items():
        assert title
        by_status.setdefault(status, set()).add(code.value)
    # LLD section 12 status table.
    assert by_status[401] == {
        "AUTH_REQUIRED",
        "TOKEN_EXPIRED",
        "PRINCIPAL_INACTIVE",
        "SESSION_REVOKED",
        "MFA_REQUIRED",
        "MFA_INVALID",
    }
    assert by_status[403] == {
        "PERMISSION_DENIED",
        "SITE_SCOPE_DENIED",
        "LICENCE_READ_ONLY",
        "LICENCE_SUSPENDED",
        "LICENCE_TERMINATED",
        "MODULE_NOT_LICENSED",
    }
    assert by_status[503] == {
        "LICENCE_UNVERIFIABLE",
        "SCHEMA_VERSION_UNSUPPORTED",
        "DB_BUSY",
        "PLATFORM_UNAVAILABLE",
    }
    assert by_status[404] == {"NOT_FOUND"}
    assert by_status[412] == {"VERSION_CONFLICT"}
    assert by_status[428] == {"PRECONDITION_REQUIRED"}
    assert by_status[429] == {"RATE_LIMITED"}
    assert "INSUFFICIENT_FREE_STOCK" in by_status[409]
    assert "REQUEST_IN_PROGRESS" in by_status[409]
