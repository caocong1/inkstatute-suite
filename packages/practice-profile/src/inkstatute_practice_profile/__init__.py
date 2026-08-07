"""inkstatute-practice-profile: multi-tenant practice profile core.

Re-exports are populated incrementally by later tasks in Plan 99-01.
"""

from .defaults import TEMPORARY_MODE_TAG, create_temporary_profile
from .model import PracticeProfile
from .secret_guard import SecretDetectedError, validate_no_secrets

__all__ = [
    "PracticeProfile",
    "SecretDetectedError",
    "TEMPORARY_MODE_TAG",
    "create_temporary_profile",
    "validate_no_secrets",
]
