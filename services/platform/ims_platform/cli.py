"""Operator command for the first ZongoVita system admin.

    ims-platform-admin create-system-admin --identifier <login> --name <display name> [--email <e>]

Staff accounts are created by system admins in the Platform Console; the very first one cannot
be. This command creates it, once: it refuses when an invited or active system admin exists.
It prints the one-time activation code (no email channel yet, #21), which the person uses to set
a password before enrolling an authenticator at first sign-in (AD-23).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from ims_common.pg import use_selector_event_loop_on_windows
from ims_platform.accounts import StaffRole
from ims_platform.registry import Actor
from ims_platform.runtime import build_runtime
from ims_platform.settings import PlatformSettings


async def _create_first_admin(identifier: str, name: str, email: str | None) -> dict[str, str]:
    runtime = await build_runtime(PlatformSettings())
    try:
        if await runtime.accounts.has_system_admin():
            raise SystemExit("a system admin already exists: create staff accounts in the Platform Console")
        created = await runtime.accounts.create_user(
            Actor("system:bootstrap"),
            login_identifier=identifier,
            display_name=name,
            email=email,
            role=StaffRole.SYSTEM_ADMIN,
        )
    finally:
        await runtime.aclose()
    return {
        "user_id": str(created.user.id),
        "login_identifier": created.user.login_identifier,
        "activation_code": created.activation_code,
        "activation_expires_at": created.activation_expires_at.isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ims-platform-admin", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-system-admin")
    create.add_argument("--identifier", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--email")
    args = parser.parse_args(argv)
    use_selector_event_loop_on_windows()
    result = asyncio.run(_create_first_admin(args.identifier, args.name, args.email))
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
