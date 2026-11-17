"""Static architecture rules, checked from the source tree (LD-01; LLD section 17).

Kept as plain functions over a directory so the rules themselves can be tested against small
synthetic trees as well as applied to the real one.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "services" / "core" / "ims_core"
PLATFORM = REPO / "services" / "platform" / "ims_platform"
CONTRACTS = REPO / "packages" / "py-contracts" / "ims_contracts"
COMMON = REPO / "packages" / "py-common" / "ims_common"
PIPELINE = REPO / "pipelines" / "database" / "ims_db_pipeline"


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.message}"


def python_files(root: Path) -> Iterator[Path]:
    yield from sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _module_name(root: Path, package: str, file: Path) -> str:
    parts = [package, *file.relative_to(root).with_suffix("").parts]
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports_of(root: Path, package: str, file: Path) -> Iterator[tuple[int, str]]:
    """Absolute dotted names imported by a file, with relative imports resolved.

    ``from a.b import c`` yields ``a.b.c``: whether ``c`` is a submodule or a name inside
    ``a.b``, that is the most specific thing the importing file depends on.
    """
    module = _module_name(root, package, file)
    current_package = module if file.name == "__init__.py" else module.rpartition(".")[0]
    tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = current_package.split(".")
                base_parts = base_parts[: len(base_parts) - (node.level - 1)]
                base = ".".join([*base_parts, *([node.module] if node.module else [])])
            else:
                base = node.module or ""
            for alias in node.names:
                yield node.lineno, f"{base}.{alias.name}" if base else alias.name


def docstring_nodes(tree: ast.AST) -> set[int]:
    """ids of the constants that are module, class or function docstrings."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                found.add(id(first.value))
    return found


def string_literals(file: Path) -> Iterator[tuple[int, str]]:
    """Every string literal in a file except docstrings."""
    tree = ast.parse(file.read_text(encoding="utf-8"))
    skip = docstring_nodes(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            yield node.lineno, node.value


# ------------------------------------------------------------------------- LD-01: module rules
def core_boundary_violations(core_root: Path = CORE) -> list[Violation]:
    """A module imports only its own files, other modules' public.py and the kernel; the kernel
    and the schema description never import a business module."""
    found: list[Violation] = []
    for file in python_files(core_root):
        rel = file.relative_to(core_root).parts
        area = rel[0] if len(rel) > 1 else ""
        own_module = rel[1] if area == "modules" and len(rel) > 2 else None
        where = "/".join(rel)
        for line, name in imports_of(core_root, "ims_core", file):
            parts = name.split(".")
            if parts[:2] != ["ims_core", "modules"] or len(parts) < 3:
                continue
            target_module = parts[2]
            if area in {"kernel", "schema"}:
                found.append(Violation(where, line, f"{area} must not import a business module ({name})"))
            elif (
                own_module is not None
                and target_module != own_module
                and (len(parts) < 4 or parts[3] != "public")
            ):
                found.append(
                    Violation(
                        where,
                        line,
                        f"module '{own_module}' may import only '{target_module}.public', not {name}",
                    )
                )
    return sorted(set(found), key=str)


def forbidden_import_violations(root: Path, package: str, forbidden: tuple[str, ...]) -> list[Violation]:
    """Deployable boundaries: a package must not import the listed top-level packages."""
    found: list[Violation] = []
    for file in python_files(root):
        for line, name in imports_of(root, package, file):
            top = name.split(".")[0]
            if top in forbidden:
                found.append(
                    Violation(file.relative_to(root).as_posix(), line, f"{package} must not import {top}")
                )
    return sorted(set(found), key=str)


# ------------------------------------------------- database access only through tenant context
_ENGINE_FACTORIES = {"create_async_engine", "create_engine", "create_pooler_engine", "create_direct_engine"}


def engine_creation_violations(
    core_root: Path = CORE, allowed: tuple[str, ...] = ("kernel/db.py",)
) -> list[Violation]:
    """In Core, only the database router may create engines: everything else must go through
    DatabaseRouter.transaction, which requires a TenantContext."""
    found: list[Violation] = []
    for file in python_files(core_root):
        rel = file.relative_to(core_root).as_posix()
        if rel in allowed:
            continue
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Name):
                names = [node.id]
            elif isinstance(node, ast.Attribute):
                names = [node.attr]
            elif isinstance(node, ast.ImportFrom):
                names = [alias.name for alias in node.names]
            found.extend(
                Violation(rel, node.lineno, f"{name} may only be used in {allowed[0]}")
                for name in names
                if name in _ENGINE_FACTORIES
            )
    return sorted(set(found), key=str)


def tenant_context_construction_violations(core_root: Path = CORE) -> list[Violation]:
    """A TenantContext is built only by the kernel (from a verified token or the work index)."""
    found: list[Violation] = []
    for file in python_files(core_root):
        rel = file.relative_to(core_root).as_posix()
        if rel.startswith("kernel/"):
            continue
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                func = node.func
                name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr
                    if isinstance(func, ast.Attribute)
                    else None
                )
                if name == "TenantContext":
                    found.append(
                        Violation(rel, node.lineno, "TenantContext may only be constructed in the kernel")
                    )
    return found


# --------------------------------------------------------------- LD-75: pooler compatibility
# SQL keywords are written in upper case throughout the codebase and function names in lower
# case, which is what keeps prose such as log messages from matching.
_SESSION_SET = re.compile(r"^\s*SET\s+(?!LOCAL\b|TRANSACTION\b)[A-Za-z_]")
_SESSION_STATE = [
    (re.compile(r"\bLISTEN\s+\w"), "LISTEN is not usable through a transaction-mode pooler"),
    (re.compile(r"\bNOTIFY\s+\w"), "NOTIFY is not used (LD-75)"),
    (re.compile(r"\bpg_notify\s*\("), "NOTIFY is not used (LD-75)"),
    (re.compile(r"\bpg_(try_)?advisory_lock(_shared)?\s*\("), "advisory locks must be transaction-scoped"),
    (re.compile(r"\bPREPARE\s+\w+\s*(\(|AS\b)"), "server-side prepared statements do not survive the pooler"),
    (re.compile(r"\bCREATE\s+(TEMP|TEMPORARY)\b"), "temporary tables are session state"),
]


def pooler_compatibility_violations(root: Path) -> list[Violation]:
    """No session-level state in application SQL: every string literal outside docstrings is inspected."""
    found: list[Violation] = []
    for file in python_files(root):
        rel = file.relative_to(root).as_posix()
        for line, value in string_literals(file):
            if _SESSION_SET.match(value):
                found.append(Violation(rel, line, "session-level SET; use SET LOCAL or a role default"))
            found.extend(
                Violation(rel, line, message) for pattern, message in _SESSION_STATE if pattern.search(value)
            )
    return found


# --------------------------------------------------------------------- migrations only expand
_CONTRACTING = [
    re.compile(r"\bDROP\s+(TABLE|COLUMN|SCHEMA|INDEX|TYPE|SEQUENCE|CONSTRAINT)\b"),
    re.compile(r"\bRENAME\s+(TO|COLUMN|CONSTRAINT)\b"),
    re.compile(r"\bALTER\s+COLUMN\s+\w+\s+(SET\s+DATA\s+)?TYPE\b"),
    re.compile(r"\bTRUNCATE\s+(TABLE\s+)?[a-z]"),
    re.compile(r"\bDELETE\s+FROM\b"),
]
_DEFINES_CODE = re.compile(r"\bCREATE\s+(OR\s+REPLACE\s+)?(TRIGGER|FUNCTION)\b")


def migration_violations(versions_dir: Path) -> list[Violation]:
    """Migrations add; drops and renames wait for a later, deliberate release (LLD 6.7)."""
    found: list[Violation] = []
    for file in python_files(versions_dir):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        downgrade = next(
            (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "downgrade"), None
        )
        if downgrade is None or not any(isinstance(n, ast.Raise) for n in ast.walk(downgrade)):
            found.append(Violation(file.name, 1, "downgrade() must refuse: migrations roll forward"))
        for line, statement in string_literals(file):
            # Trigger and function definitions name DELETE and TRUNCATE as the events they guard.
            if _DEFINES_CODE.search(statement):
                continue
            found.extend(
                Violation(file.name, line, f"contracting statement: {pattern.pattern}")
                for pattern in _CONTRACTING
                if pattern.search(statement)
            )
    return found
