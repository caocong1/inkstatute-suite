"""Role-based access control for InkStatute admin APIs."""

from .guard import RbacGuard
from .matrix import PERMISSIONS_MATRIX
from .roles import Role

__all__ = [
    "PERMISSIONS_MATRIX",
    "Role",
    "RbacGuard",
]
