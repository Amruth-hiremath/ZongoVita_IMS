"""Schema versions this release of Core can serve (LLD 6.7, AD-29).

A release declares schema head H and supports {H-1, H}: during a rolling migration some
customer databases are still one version behind, and the application must work on both.
A test keeps ``SCHEMA_HEAD`` equal to the head of services/core/migrations.
"""

#: Head revision of services/core/migrations for this release.
SCHEMA_HEAD = "0004"

#: Previous release's head, or None for the first release.
SCHEMA_PREVIOUS: str | None = "0003"

SCHEMA_SUPPORTED = frozenset(v for v in (SCHEMA_HEAD, SCHEMA_PREVIOUS) if v is not None)
