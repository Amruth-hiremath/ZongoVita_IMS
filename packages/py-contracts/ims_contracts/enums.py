"""Enumerations shared across services (LLD sections 1, 4 and 5.4)."""

from enum import StrEnum


class PrincipalType(StrEnum):
    """Who is acting on a request (LLD section 1, "Principal")."""

    USER = "user"
    API_CLIENT = "api_client"
    SUPPORT = "support"


class ActorType(StrEnum):
    """audit.audit_log.actor_type (LLD 5.4)."""

    USER = "user"
    API_CLIENT = "api_client"
    SUPPORT = "support"
    SYSTEM = "system"
    BREAK_GLASS = "break_glass"


class CustomerStatus(StrEnum):
    """platform.customers.status (LLD section 4)."""

    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class LicenceRecordStatus(StrEnum):
    """platform.licences.record_status (LLD section 4)."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class Placement(StrEnum):
    """Where a customer database lives (AD-17)."""

    SHARED = "shared"
    DEDICATED = "dedicated"


class DatabaseStatus(StrEnum):
    """platform.customer_databases.status (LLD section 4)."""

    CREATING = "creating"
    READY = "ready"
    MIGRATING = "migrating"
    FAILED = "failed"
    RETIRED = "retired"


class ChangeType(StrEnum):
    """platform.change_feed.change_type (LLD section 4)."""

    LICENCE = "licence"
    STATUS = "status"
    DATABASE = "database"
    DIRECTORY = "directory"
    GXP = "gxp"
    PLACEMENT = "placement"


class WorkKind(StrEnum):
    """platform.work_pending.kind (LLD section 4, LD-76)."""

    OUTBOX = "outbox"
    JOBS = "jobs"
    RESERVATIONS = "reservations"
    GRANTS = "grants"


class LicenceModule(StrEnum):
    """Licensable module tags carried by every route and job (LD-72).

    This is the current tagging; the commercial module list is owned by Product (open item #5).
    """

    CORE = "ims.core"
    REPLENISHMENT = "ims.replenishment"
    SUPPLIER_REGISTER = "ims.supplier_register"
    INTEGRATION = "ims.integration"
