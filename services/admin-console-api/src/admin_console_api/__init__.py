"""Read-only Admin Console API for InkStatute V2 operator views."""

from .api import handle_admin_get
from .auth import check_auth_header, resolve_admin_token
from .gates import handle_gates, run_gate_summary
from .health import HEALTH_ALLOWED_FIELDS, handle_health, project_health
from .routes import ROUTE_PREFIXES

__all__ = [
    "handle_admin_get",
    "resolve_admin_token",
    "check_auth_header",
    "handle_health",
    "project_health",
    "HEALTH_ALLOWED_FIELDS",
    "handle_gates",
    "run_gate_summary",
    "ROUTE_PREFIXES",
]
