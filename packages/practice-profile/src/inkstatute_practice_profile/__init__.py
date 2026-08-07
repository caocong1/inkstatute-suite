"""inkstatute-practice-profile: multi-tenant practice profile core.

Re-exports are populated incrementally by later tasks in Plan 99-01.
"""

from .defaults import TEMPORARY_MODE_TAG, create_temporary_profile
from .injector import (
    PracticeProfileInjector,
    ProfileInjectionResult,
    SkillNotFoundError,
)
from .model import PracticeProfile
from .rbac_check import (
    PROFILE_READ_ROLES,
    PROFILE_WRITE_ROLES,
    check_read_access,
    check_tenant_access,
    check_write_access,
)
from .secret_guard import SecretDetectedError, validate_no_secrets
from .store import InMemoryPracticeProfileStore, PracticeProfileStore

__all__ = [
    "InMemoryPracticeProfileStore",
    "PROFILE_READ_ROLES",
    "PROFILE_WRITE_ROLES",
    "PracticeProfile",
    "PracticeProfileInjector",
    "PracticeProfileStore",
    "ProfileInjectionResult",
    "SecretDetectedError",
    "SkillNotFoundError",
    "TEMPORARY_MODE_TAG",
    "check_read_access",
    "check_tenant_access",
    "check_write_access",
    "create_temporary_profile",
    "validate_no_secrets",
]
