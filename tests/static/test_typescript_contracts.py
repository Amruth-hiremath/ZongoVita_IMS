"""The TypeScript contracts used by the web apps mirror the Python ones.

packages/api-client is written by hand until Core publishes an OpenAPI document (LLD section 2:
"TypeScript client from OpenAPI"). Until then these tests keep the two sides from drifting.
"""

from __future__ import annotations

import re
from pathlib import Path

from ims_contracts.enums import LicenceModule
from ims_contracts.errors import ErrorCode
from ims_contracts.licence import LicenceState
from ims_contracts.permissions import CATALOGUE, RESERVED_TO_SUPER_ADMIN, SEEDED_BY_CODE

API_CLIENT = Path(__file__).resolve().parents[2] / "packages" / "api-client" / "src"
TENANT_WEB = Path(__file__).resolve().parents[2] / "apps" / "tenant-web" / "src"


def _string_array(source: str, name: str) -> list[str]:
    match = re.search(rf"export const {name} = \[(.*?)\] as const", source, re.DOTALL)
    assert match, f"{name} not found"
    return re.findall(r'"([^"]+)"', match.group(1))


def test_error_codes_match() -> None:
    codes = _string_array((API_CLIENT / "problem.ts").read_text(encoding="utf-8"), "ERROR_CODES")
    assert len(codes) == len(set(codes))
    assert set(codes) == {code.value for code in ErrorCode}


def test_licence_states_match() -> None:
    states = _string_array((API_CLIENT / "licence.ts").read_text(encoding="utf-8"), "LICENCE_STATES")
    assert states == [state.value for state in LicenceState]


def test_permission_catalogue_matches_core() -> None:
    """LLD section 7: the web app's catalogue is Core's, code for code, scope for scope."""
    source = (API_CLIENT / "permissions.ts").read_text(encoding="utf-8")
    entries = re.findall(r'^\s*"([^"]+)": \{ siteScoped: (true|false) \},$', source, re.MULTILINE)
    assert [code for code, _ in entries] == [p.code for p in CATALOGUE], "same codes, same order"
    assert {code for code, flag in entries if flag == "true"} == {p.code for p in CATALOGUE if p.site_scoped}
    reserved = set(
        re.findall(r'"(access\.[a-z_.]+)"', source.split("RESERVED_TO_SUPER_ADMIN")[1].split("];")[0])
    )
    assert reserved == RESERVED_TO_SUPER_ADMIN


def _typed_array(source: str, name: str) -> list[str]:
    match = re.search(rf"export const {name}: readonly PermissionCode\[\] = \[(.*?)\];", source, re.DOTALL)
    assert match, f"{name} not found"
    return re.findall(r'"([^"]+)"', match.group(1))


def test_seeded_user_types_match_core() -> None:
    """LLD 5.1 seeded roles: the sample personas use the same defaults as provisioning."""
    source = (API_CLIENT / "permissions.ts").read_text(encoding="utf-8")
    for number in (2, 3, 4):
        listed = _typed_array(source, f"USER_TYPE_{number}")
        assert len(listed) == len(set(listed))
        assert set(listed) == SEEDED_BY_CODE[f"user_type_{number}"].permissions, number
    assert "!RESERVED_TO_SUPER_ADMIN.includes(code)" in source.split("export const USER_TYPE_1")[1]


def test_sample_personas_use_real_module_tags() -> None:
    source = (TENANT_WEB / "fixtures" / "personas.ts").read_text(encoding="utf-8")
    modules = re.search(r"modules: \[(.*?)\]", source, re.DOTALL)
    assert modules
    assert set(re.findall(r'"([^"]+)"', modules.group(1))) == {module.value for module in LicenceModule}


def test_fixtures_are_reached_only_through_the_data_layer() -> None:
    """Sample data must stay swappable in one place (Docs/UI_Implementation.md, rule 4)."""
    allowed = {TENANT_WEB / "session" / "server.ts"}
    offenders = []
    for file in [*TENANT_WEB.rglob("*.ts"), *TENANT_WEB.rglob("*.tsx")]:
        relative = file.relative_to(TENANT_WEB).as_posix()
        if relative.startswith(("data/", "fixtures/")) or file in allowed:
            continue
        if re.search(r"""from ["']@/fixtures""", file.read_text(encoding="utf-8")):
            offenders.append(relative)
    assert offenders == []


def test_no_inline_styles_in_the_web_apps() -> None:
    """The apps run under a strict Content Security Policy; a style attribute would be dropped."""
    root = Path(__file__).resolve().parents[2]
    offenders = []
    for base in (root / "apps", root / "packages" / "ui"):
        for file in base.rglob("*.tsx"):
            if "node_modules" in file.parts or ".next" in file.parts:
                continue
            if re.search(r"\bstyle=\{", file.read_text(encoding="utf-8")):
                offenders.append(file.relative_to(root).as_posix())
    assert offenders == []


def test_ui_dependency_tables_are_current() -> None:
    """Docs/UI_Implementation.md lists every endpoint the screens wait for, generated from code."""
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    import pytest  # noqa: PLC0415

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(  # noqa: S603 - fixed arguments
        [node, "tools/ui-dependencies.mjs", "--check"], cwd=root, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_platform_enumerations_match() -> None:
    """The Platform Console reads /platform/v1 with the Platform Service's own vocabulary."""
    from ims_contracts.enums import CustomerStatus  # noqa: PLC0415
    from ims_platform.accounts import StaffRole  # noqa: PLC0415
    from ims_platform.provisioning import STEPS  # noqa: PLC0415

    source = (API_CLIENT / "platform.ts").read_text(encoding="utf-8")
    assert _string_array(source, "STAFF_ROLES") == [role.value for role in StaffRole]
    assert _string_array(source, "CUSTOMER_STATUSES") == [status.value for status in CustomerStatus]
    assert _string_array(source, "PROVISIONING_STEPS") == [*STEPS, "done"]
