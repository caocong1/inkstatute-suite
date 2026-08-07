"""inkstatute-practice-profile: multi-tenant practice profile core.

Re-exports are populated incrementally by later tasks in Plan 99-01.
"""

from .defaults import TEMPORARY_MODE_TAG, create_temporary_profile
from .model import PracticeProfile

__all__ = [
    "PracticeProfile",
    "TEMPORARY_MODE_TAG",
    "create_temporary_profile",
]
